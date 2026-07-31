"""Edge node registry -- onboarding a state is a config change, not a code change.

NFR-5 requires that bringing a new state online touches only a registry entry,
never central's code path. This module is that registry: it discovers deployed
node artifacts, tracks enable/disable state and health, and answers the single
question the router asks -- "is there a qualified edge node for this state?"

The registry file (``edge_registry.json``) is written next to the edge
artifacts and is safe to hand-edit; anything absent from it is derived from
what is actually on disk, so a freshly trained node is picked up without
editing anything at all.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import joblib

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EDGE_DIR = PROJECT_ROOT / "backend" / "artifacts" / "edge" / "advisor"
SHARED_DIR = EDGE_DIR / "_shared"
CENTRAL_DIR = PROJECT_ROOT / "backend" / "artifacts" / "central" / "advisor"
REGISTRY_FILE = EDGE_DIR / "edge_registry.json"

#: Consecutive failures before a node is circuit-broken out of rotation.
FAILURE_THRESHOLD = 3
#: Seconds a tripped breaker stays open before a half-open retry.
BREAKER_COOLDOWN_S = 60.0


@dataclass
class EdgeNode:
    """One state's edge node."""
    state: str
    enabled: bool = True
    promoted: bool = True
    gap: Optional[float] = None
    algorithm: Optional[str] = None
    calibration_slope: float = 1.0
    calibration_intercept: float = 0.0

    # runtime health, not persisted
    consecutive_failures: int = field(default=0, repr=False)
    breaker_opened_at: Optional[float] = field(default=None, repr=False)

    def artifact_path(self) -> Path:
        return EDGE_DIR / self.state / "yield_model.pkl"

    def exists(self) -> bool:
        return self.artifact_path().exists()

    def is_healthy(self) -> bool:
        """False while the circuit breaker is open; half-opens after cooldown."""
        if self.breaker_opened_at is None:
            return True
        if time.time() - self.breaker_opened_at >= BREAKER_COOLDOWN_S:
            logger.info("edge[%s]: breaker half-open, retrying", self.state)
            self.breaker_opened_at = None
            self.consecutive_failures = 0
            return True
        return False

    def is_available(self) -> bool:
        return self.enabled and self.promoted and self.exists() and self.is_healthy()

    def record_success(self) -> None:
        self.consecutive_failures = 0

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= FAILURE_THRESHOLD and self.breaker_opened_at is None:
            self.breaker_opened_at = time.time()
            logger.warning("edge[%s]: breaker OPEN after %d failures -> central",
                           self.state, self.consecutive_failures)


class EdgeRegistry:
    """Thread-safe registry of edge nodes with lazy model loading."""

    def __init__(self) -> None:
        self._nodes: Dict[str, EdgeNode] = {}
        self._models: Dict[str, object] = {}
        self._shared: Dict[str, object] = {}
        self._lock = threading.RLock()
        self._loaded = False

    # ── discovery ──────────────────────────────────────────────────────────

    def load(self, force: bool = False) -> None:
        with self._lock:
            if self._loaded and not force:
                return
            self._nodes.clear()

            # Nodes present on disk are live by default -- training a state is
            # enough to onboard it; the JSON file only overrides.
            if EDGE_DIR.exists():
                for meta_path in EDGE_DIR.glob("*/node_metadata.json"):
                    try:
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                        state = meta["state"]
                        self._nodes[state] = EdgeNode(
                            state=state,
                            promoted=bool(meta.get("promoted", False)),
                            gap=meta.get("gap"),
                            algorithm=meta.get("algorithm"),
                            calibration_slope=float(meta.get("calibration_slope", 1.0)),
                            calibration_intercept=float(meta.get("calibration_intercept", 0.0)),
                        )
                    except Exception as exc:
                        logger.warning("registry: bad node metadata %s: %s", meta_path, exc)

            # Registry file overlay: enable/disable without retraining.
            if REGISTRY_FILE.exists():
                try:
                    overlay = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
                    for state, cfg in overlay.get("nodes", {}).items():
                        node = self._nodes.get(state) or EdgeNode(state=state)
                        node.enabled = bool(cfg.get("enabled", node.enabled))
                        if "promoted" in cfg:
                            node.promoted = bool(cfg["promoted"])
                        self._nodes[state] = node
                except Exception as exc:
                    logger.warning("registry: cannot read %s: %s", REGISTRY_FILE, exc)

            self._loaded = True
            live = [s for s, n in self._nodes.items() if n.is_available()]
            logger.info("registry: %d node(s) discovered, %d available",
                        len(self._nodes), len(live))

    def save(self) -> None:
        """Persist the enable/disable overlay."""
        with self._lock:
            EDGE_DIR.mkdir(parents=True, exist_ok=True)
            payload = {
                "nodes": {
                    s: {"enabled": n.enabled, "promoted": n.promoted, "gap": n.gap}
                    for s, n in sorted(self._nodes.items())
                }
            }
            REGISTRY_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # ── queries ────────────────────────────────────────────────────────────

    def get(self, state: str) -> Optional[EdgeNode]:
        self.load()
        return self._nodes.get(state)

    def is_available(self, state: str) -> bool:
        node = self.get(state)
        return node is not None and node.is_available()

    def available_states(self) -> List[str]:
        self.load()
        return sorted(s for s, n in self._nodes.items() if n.is_available())

    def all_nodes(self) -> Dict[str, EdgeNode]:
        self.load()
        return dict(self._nodes)

    # ── model access ───────────────────────────────────────────────────────

    def yield_model(self, state: str):
        """Lazily load and cache a state's yield model."""
        with self._lock:
            if state not in self._models:
                node = self.get(state)
                if node is None or not node.exists():
                    raise FileNotFoundError(f"no edge yield model for '{state}'")
                self._models[state] = joblib.load(node.artifact_path())
            return self._models[state]

    def shared_model(self, name: str):
        """Lazily load a compressed national replica shared by every node."""
        with self._lock:
            if name not in self._shared:
                path = SHARED_DIR / f"{name}_model.pkl"
                if not path.exists():
                    raise FileNotFoundError(f"no shared edge model '{name}' at {path}")
                self._shared[name] = joblib.load(path)
            return self._shared[name]

    def shared_ready(self) -> bool:
        needed = ["crop", "sunlight", "irrigation_type", "irrigation_need"]
        return all((SHARED_DIR / f"{n}_model.pkl").exists() for n in needed)

    # ── administration (used by the scalability proof) ─────────────────────

    def set_enabled(self, state: str, enabled: bool) -> bool:
        """Enable/disable a node at runtime. Returns False if unknown."""
        with self._lock:
            node = self.get(state)
            if node is None:
                return False
            node.enabled = enabled
            if enabled:
                node.consecutive_failures = 0
                node.breaker_opened_at = None
            self.save()
            logger.info("registry: %s -> %s", state, "enabled" if enabled else "disabled")
            return True

    def status(self) -> Dict[str, object]:
        self.load()
        return {
            "total_nodes": len(self._nodes),
            "available": self.available_states(),
            "shared_replicas_ready": self.shared_ready(),
            "nodes": {
                s: {
                    "enabled": n.enabled,
                    "promoted": n.promoted,
                    "artifact_present": n.exists(),
                    "healthy": n.is_healthy(),
                    "available": n.is_available(),
                    "gap": n.gap,
                    "algorithm": n.algorithm,
                    "consecutive_failures": n.consecutive_failures,
                }
                for s, n in sorted(self._nodes.items())
            },
        }


#: Process-wide singleton.
registry = EdgeRegistry()
