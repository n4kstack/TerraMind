"""Two-mode router: serve from the state's edge node, else central.

Exactly two modes exist (Hard Constraint 1). The router reads the ``state``
field already present in the request schema -- no new input field is
introduced (Hard Constraint 2) -- and decides where inference happens:

    edge     a healthy, promoted node exists for this state AND the edge
             prediction clears the confidence threshold
    central  everything else: no node, disabled, circuit-broken, or the
             edge model was not confident enough for this particular request

Central can absorb 100% of traffic at any time and is never removed from the
path (Hard Constraint 4 / FR-1).

The confidence signal is strictly internal. It informs routing and is written
to the fallback log; it is never added to the response body, because the output
schema is frozen (Hard Constraint 2, SRD section 10).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import joblib
import numpy as np
import pandas as pd

from ml.advisor_edge import MODE_CENTRAL, MODE_EDGE
from ml.advisor_edge import candidates as C
from ml.advisor_edge import features as F
from ml.advisor_edge.registry import CENTRAL_DIR, registry

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FALLBACK_LOG = PROJECT_ROOT / "backend" / "artifacts" / "edge" / "fallback_events.jsonl"

#: Minimum crop-classifier confidence for an edge answer to be trusted.
#: Below this the request is served by central instead (FR-4).
CONFIDENCE_THRESHOLD = 0.45


def _yield_ceiling() -> float:
    """Inference ceiling fitted during central training."""
    try:
        meta = json.loads((CENTRAL_DIR / "central_metadata.json").read_text(encoding="utf-8"))
        return float(meta["targets"]["yield_predictor"]["yield_ceiling"])
    except Exception:
        return C.DEFAULT_YIELD_CEILING


@dataclass
class RouteDecision:
    mode: str
    state: str
    reason: str
    confidence: Optional[float] = None
    edge_available: bool = False
    latency_ms: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════
# Feature construction -- reuses the shared pipeline so central and edge see
# byte-identical inputs.
# ═══════════════════════════════════════════════════════════════════════════

def _crop_vector(payload: Dict[str, Any], scaler) -> np.ndarray:
    row = pd.DataFrame([{
        "N": float(payload["N"]), "P": float(payload["P"]), "K": float(payload["K"]),
        "temperature": float(payload["temperature"]),
        "humidity": float(payload["humidity"]),
        "ph": float(payload["ph"]), "rainfall": float(payload["rainfall"]),
    }])
    row = F.engineer_crop_features(row)
    return scaler.transform(row[F.CROP_ALL_FEATURES].values.astype(np.float64))


def _irrigation_vector(payload: Dict[str, Any], crop: str, preprocessor) -> np.ndarray:
    row = pd.DataFrame([{
        "ph": float(payload["ph"]),
        "temperature": float(payload["temperature"]),
        "humidity": float(payload["humidity"]),
        "rainfall": float(payload["rainfall"]),
        "crop": F.normalise_string(crop),
        "soil_type": F.normalise_string(payload.get("soil_type") or "loamy"),
        "season": F.normalise_string(payload.get("season") or "kharif"),
    }])
    row = F.engineer_irrigation_features(row)
    return preprocessor.transform(row[F.IRR_ALL_FEATURES])


def _yield_vector(payload: Dict[str, Any], crop: str, encoders) -> np.ndarray:
    row = pd.DataFrame([{
        "crop": F.normalise_string(crop),
        "state": F.normalise_state(payload.get("state") or ""),
        "district": F.normalise_string(payload.get("district") or ""),
        "season": F.normalise_string(payload.get("season") or "kharif"),
    }])
    return encoders.transform(row)


# ═══════════════════════════════════════════════════════════════════════════
# Predictors
# ═══════════════════════════════════════════════════════════════════════════

class _ArtifactCache:
    """Lazy, thread-safe loader for the central artifact set."""

    def __init__(self) -> None:
        self._cache: Dict[str, Any] = {}
        self._lock = threading.RLock()

    def get(self, name: str):
        with self._lock:
            if name not in self._cache:
                path = CENTRAL_DIR / f"{name}.pkl"
                if not path.exists():
                    raise FileNotFoundError(f"central artifact missing: {path}")
                self._cache[name] = joblib.load(path)
            return self._cache[name]

    def ready(self) -> bool:
        needed = ["crop_model", "crop_scaler", "crop_label_encoder",
                  "irrigation_preprocessor", "sunlight_model",
                  "irrigation_type_model", "irrigation_type_encoder",
                  "irrigation_need_model", "irrigation_need_encoder",
                  "yield_model", "yield_encoders"]
        return all((CENTRAL_DIR / f"{n}.pkl").exists() for n in needed)


central_artifacts = _ArtifactCache()


def _decode_top3(proba: np.ndarray, label_encoder) -> tuple[list, str, float]:
    order = np.argsort(proba)[::-1][:3]
    top3 = [
        {"crop": str(label_encoder.classes_[i]), "confidence": round(float(proba[i]), 4)}
        for i in order
    ]
    return top3, top3[0]["crop"], top3[0]["confidence"]


def predict_central(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Full five-target inference using the central reference models."""
    scaler = central_artifacts.get("crop_scaler")
    le = central_artifacts.get("crop_label_encoder")
    crop_model = central_artifacts.get("crop_model")

    Xc = _crop_vector(payload, scaler)
    proba = crop_model.predict_proba(Xc)[0]
    top3, crop, confidence = _decode_top3(proba, le)

    pre = central_artifacts.get("irrigation_preprocessor")
    Xi = _irrigation_vector(payload, crop, pre)
    sunlight = F.scalar(central_artifacts.get("sunlight_model").predict(Xi))

    t_enc = central_artifacts.get("irrigation_type_encoder")
    t_model = central_artifacts.get("irrigation_type_model")
    t_proba = t_model.predict_proba(Xi)[0]
    irr_type = str(t_enc.classes_[int(np.argmax(t_proba))])
    type_probs = {str(c): round(float(p), 4) for c, p in zip(t_enc.classes_, t_proba)}

    n_enc = central_artifacts.get("irrigation_need_encoder")
    n_model = central_artifacts.get("irrigation_need_model")
    irr_need = str(n_enc.classes_[int(F.scalar(n_model.predict(Xi)))])

    encoders = central_artifacts.get("yield_encoders")
    Xy = _yield_vector(payload, crop, encoders)
    expected_yield = float(C.clamp_yield(F.scalar(central_artifacts.get("yield_model").predict(Xy)), _yield_ceiling()))

    return {
        "crop": crop, "top_3": top3, "confidence": confidence,
        "sunlight_hours": round(float(np.clip(sunlight, 3.0, 12.0)), 1),
        "irrigation_type": irr_type,
        "irrigation_need": irr_need,
        "irrigation_type_probabilities": type_probs,
        "expected_yield": round(max(expected_yield, 0.0), 4),
    }


def predict_edge(payload: Dict[str, Any], state: str) -> Dict[str, Any]:
    """Full five-target inference served entirely from the state's edge node.

    Four models are compressed national replicas held on every node; the yield
    model is that state's own, trained only on its rows and locally calibrated.
    Nothing here contacts central, which is what gives the bandwidth and
    data-locality properties in NFR-4.
    """
    scaler = central_artifacts.get("crop_scaler")
    le = central_artifacts.get("crop_label_encoder")

    Xc = _crop_vector(payload, scaler)
    proba = registry.shared_model("crop").predict_proba(Xc)[0]
    top3, crop, confidence = _decode_top3(proba, le)

    pre = central_artifacts.get("irrigation_preprocessor")
    Xi = _irrigation_vector(payload, crop, pre)
    sunlight = F.scalar(registry.shared_model("sunlight").predict(Xi))

    t_enc = central_artifacts.get("irrigation_type_encoder")
    t_proba = registry.shared_model("irrigation_type").predict_proba(Xi)[0]
    irr_type = str(t_enc.classes_[int(np.argmax(t_proba))])
    type_probs = {str(c): round(float(p), 4) for c, p in zip(t_enc.classes_, t_proba)}

    n_enc = central_artifacts.get("irrigation_need_encoder")
    irr_need = str(n_enc.classes_[int(F.scalar(registry.shared_model("irrigation_need").predict(Xi)))])

    encoders = central_artifacts.get("yield_encoders")
    Xy = _yield_vector(payload, crop, encoders)
    node = registry.get(state)
    raw = float(C.clamp_yield(F.scalar(registry.yield_model(state).predict(Xy)), _yield_ceiling()))
    calibrated = float(C.clamp_yield(
        raw * (node.calibration_slope if node else 1.0)
        + (node.calibration_intercept if node else 0.0),
        _yield_ceiling(),
    ))

    return {
        "crop": crop, "top_3": top3, "confidence": confidence,
        "sunlight_hours": round(float(np.clip(sunlight, 3.0, 12.0)), 1),
        "irrigation_type": irr_type,
        "irrigation_need": irr_need,
        "irrigation_type_probabilities": type_probs,
        "expected_yield": round(max(calibrated, 0.0), 4),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Router
# ═══════════════════════════════════════════════════════════════════════════

def _log_fallback(state: str, reason: str, confidence: Optional[float]) -> None:
    """Record a fallback so retraining can be prioritised (FR-4)."""
    try:
        FALLBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
        with FALLBACK_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "state": state, "reason": reason, "confidence": confidence,
            }) + "\n")
    except Exception:
        pass  # logging must never break serving


def route_and_predict(payload: Dict[str, Any]) -> tuple[Dict[str, Any], RouteDecision]:
    """Pick a mode, run inference, return (predictions, decision).

    Routing is automatic and state-based (FR-3): a qualified node serves its
    own state rather than deferring to central (Hard Constraint 6). A caller
    may still pin a request to central by passing ``mode="central"``; that is
    an explicit choice, not the system defaulting, so it does not conflict
    with Constraint 6.

    Falls back to central on any edge failure, so the worst case is exactly
    pre-refactor behaviour.
    """
    state = F.normalise_state(payload.get("state") or payload.get("state_name") or "")
    t0 = time.perf_counter()

    # Explicit central pin from the caller.
    requested = str(payload.get("mode") or "").strip().lower()
    if requested == MODE_CENTRAL:
        out = predict_central(payload)
        return out, RouteDecision(
            MODE_CENTRAL, state, "explicit_central", out["confidence"],
            registry.is_available(state),
            round((time.perf_counter() - t0) * 1000, 3),
        )

    if not registry.is_available(state):
        reason = "no_edge_node" if registry.get(state) is None else "node_unavailable"
        _log_fallback(state, reason, None)
        out = predict_central(payload)
        return out, RouteDecision(
            MODE_CENTRAL, state, reason, out["confidence"], False,
            round((time.perf_counter() - t0) * 1000, 3),
        )

    if not registry.shared_ready():
        _log_fallback(state, "shared_replicas_missing", None)
        out = predict_central(payload)
        return out, RouteDecision(
            MODE_CENTRAL, state, "shared_replicas_missing", out["confidence"], True,
            round((time.perf_counter() - t0) * 1000, 3),
        )

    node = registry.get(state)
    try:
        out = predict_edge(payload, state)
    except Exception as exc:
        node.record_failure()
        logger.warning("edge[%s] inference failed: %s", state, exc)
        _log_fallback(state, f"edge_error: {exc}", None)
        out = predict_central(payload)
        return out, RouteDecision(
            MODE_CENTRAL, state, "edge_error", out["confidence"], True,
            round((time.perf_counter() - t0) * 1000, 3),
        )

    if out["confidence"] < CONFIDENCE_THRESHOLD:
        _log_fallback(state, "low_confidence", out["confidence"])
        central_out = predict_central(payload)
        return central_out, RouteDecision(
            MODE_CENTRAL, state, "low_confidence", out["confidence"], True,
            round((time.perf_counter() - t0) * 1000, 3),
        )

    node.record_success()
    return out, RouteDecision(
        MODE_EDGE, state, "edge_served", out["confidence"], True,
        round((time.perf_counter() - t0) * 1000, 3),
    )


def router_status() -> Dict[str, Any]:
    return {
        "modes": [MODE_CENTRAL, MODE_EDGE],
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "central_ready": central_artifacts.ready(),
        "registry": registry.status(),
    }
