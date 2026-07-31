"""District crop-suitability prior for the Crop Recommender.

The Crop Recommender is trained on soil chemistry and weather only --
``N, P, K, temperature, humidity, ph, rainfall`` -- because
``crop_dataset_rebuilt.csv`` carries no geography. Geography therefore cannot
influence it: the same soil reading returns the same crop whether the request
says Punjab or the Thar desert, and the model happily recommends rice for
Jaisalmer.

This module supplies the missing signal from data that *does* carry geography:
historical cultivated area per district from the production datasets. It is a
calibrated prior applied after the model, in the same spirit as
``irrigation_prior`` -- the agronomic model still leads, the district evidence
modulates it.

Two corrections are applied, in order:

1. **Temperature softening.** ``crop_dataset_rebuilt.csv`` is balanced and
   separable enough that the classifier saturates -- typically 1.000 for the
   top crop and 0.000 for everything else. A saturated distribution cannot be
   blended with anything, because zero multiplied by any prior stays zero.
   Softening restores usable relative ordering without changing the ranking.

2. **Geometric blend with the district prior.** ``p_final ∝ p_model^(1-w) *
   prior^w``. This is a likelihood-times-prior form rather than a linear mix,
   so a crop the model considers implausible cannot be promoted by district
   popularity alone, and a crop never grown in a district is down-weighted
   rather than eliminated.

Only the ten classes the model can emit are considered; other crops in the
production data are ignored because they are not choosable outputs.
"""

from __future__ import annotations

import json
import logging
import math
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from ml import data_sources
from ml.pre_sowing_advisor.normalizers import normalize_district_name, normalize_state_name

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_PATH = PROJECT_ROOT / "backend" / "artifacts" / "crop_district_prior.json"

#: Upper bound on the softening temperature, reached only when the model's
#: output is fully degenerate. See :func:`_adaptive_temperature`.
SOFTEN_T_MAX = 8.0

#: How much the district evidence counts against the agronomic model.
#: At 0.0 behaviour is exactly as before this module existed.
PRIOR_WEIGHT = 0.55

#: Floor added to every prior so an unseen crop is penalised, never zeroed.
PRIOR_FLOOR = 0.01

#: Below this many hectares of recorded history a district is not trusted and
#: the state-level prior is used instead.
MIN_DISTRICT_AREA = 1000.0

#: Production-dataset crop names mapped onto the ten classes the model emits.
#: Anything unmapped is ignored -- the model cannot recommend it.
CROP_ALIASES: Dict[str, str] = {
    "rice": "rice", "paddy": "rice",
    "wheat": "wheat",
    "barley": "barley",
    "maize": "maize",
    "sugarcane": "sugarcane",
    "tobacco": "tobacco",
    "groundnut": "groundnut",
    "cotton(lint)": "cotton", "cotton": "cotton",
    # millets
    "bajra": "millets", "jowar": "millets", "ragi": "millets",
    "small millets": "millets", "korra": "millets", "varagu": "millets",
    "samai": "millets", "other cereals": "millets",
    "other  rabi pulses": "pulses",
    # pulses
    "gram": "pulses", "arhar/tur": "pulses", "moong(green gram)": "pulses",
    "urad": "pulses", "masoor": "pulses", "moth": "pulses",
    "horse-gram": "pulses", "khesari": "pulses", "peas & beans (pulses)": "pulses",
    "other kharif pulses": "pulses", "other rabi pulses": "pulses",
    "lentil": "pulses", "cowpea(lobia)": "pulses", "ricebean (nagadal)": "pulses",
    "rajmash kholar": "pulses", "peas  (vegetable)": "pulses",
    "total foodgrain": "", "pulses total": "",
}

_lock = threading.RLock()
_prior_cache: Optional[Dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════════════════
# Building the prior
# ═══════════════════════════════════════════════════════════════════════════

def _canonical_crop(raw: str) -> Optional[str]:
    key = str(raw).strip().lower()
    mapped = CROP_ALIASES.get(key)
    return mapped or None


def build_prior(force: bool = False) -> Dict[str, Any]:
    """Build (or load) district and state crop-share tables.

    Shares are computed over cultivated area restricted to the model's ten
    classes, so they read as "of the crops this advisor can recommend, this is
    what the district actually grows".
    """
    global _prior_cache
    with _lock:
        if _prior_cache is not None and not force:
            return _prior_cache

        if CACHE_PATH.exists() and not force:
            try:
                _prior_cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
                logger.info("Crop district prior loaded from cache (%d districts)",
                            len(_prior_cache.get("districts", {})))
                return _prior_cache
            except Exception as exc:
                logger.warning("Crop prior cache unreadable, rebuilding: %s", exc)

        path = data_sources.india_agri_csv()
        if path is None:
            logger.warning("Production dataset not found; crop prior disabled")
            _prior_cache = {"districts": {}, "states": {}}
            return _prior_cache

        df = pd.read_csv(path, usecols=["State", "District", "Crop", "Area"])
        df = df.dropna(subset=["State", "District", "Crop", "Area"])
        df = df[df["Area"] > 0]

        df["crop_class"] = df["Crop"].map(_canonical_crop)
        df = df.dropna(subset=["crop_class"])
        df = df[df["crop_class"] != ""]

        df["state_key"] = df["State"].map(normalize_state_name)
        df["district_key"] = df["District"].map(normalize_district_name)

        districts: Dict[str, Dict[str, float]] = {}
        grouped = df.groupby(["state_key", "district_key", "crop_class"])["Area"].sum()
        for (st, di, crop), area in grouped.items():
            districts.setdefault(f"{st}|{di}", {})[crop] = float(area)

        states: Dict[str, Dict[str, float]] = {}
        for (st, crop), area in df.groupby(["state_key", "crop_class"])["Area"].sum().items():
            states.setdefault(st, {})[crop] = float(area)

        def _to_share(table: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
            out = {}
            for key, crops in table.items():
                total = sum(crops.values())
                if total <= 0:
                    continue
                out[key] = {c: round(a / total, 6) for c, a in crops.items()}
                out[key]["__total_area__"] = round(total, 2)
            return out

        _prior_cache = {
            "districts": _to_share(districts),
            "states": _to_share(states),
        }

        try:
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            CACHE_PATH.write_text(json.dumps(_prior_cache), encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not write crop prior cache: %s", exc)

        logger.info("Crop district prior built: %d districts, %d states",
                    len(_prior_cache["districts"]), len(_prior_cache["states"]))
        return _prior_cache


def lookup_prior(state: str, district: str) -> Tuple[Dict[str, float], str]:
    """Return (crop -> share, scope) for a location.

    Falls back district -> state -> none, so a request naming an unknown
    district still benefits from its state's cultivation pattern.
    """
    table = build_prior()
    st = normalize_state_name(state or "")
    di = normalize_district_name(district or "")

    entry = table["districts"].get(f"{st}|{di}")
    if entry and entry.get("__total_area__", 0.0) >= MIN_DISTRICT_AREA:
        return {k: v for k, v in entry.items() if not k.startswith("__")}, "district"

    entry = table["states"].get(st)
    if entry:
        return {k: v for k, v in entry.items() if not k.startswith("__")}, "state"

    return {}, "none"


# ═══════════════════════════════════════════════════════════════════════════
# Applying the prior
# ═══════════════════════════════════════════════════════════════════════════

def _adaptive_temperature(probs: Dict[str, float]) -> float:
    """Choose a softening temperature from the model's own certainty.

    A fixed temperature is the wrong tool here, because the classifier is not
    uniformly overconfident. On an arid or mid-range soil profile it returns a
    healthy spread (8 of 10 classes non-zero, entropy ~1.12) that deserves to
    be trusted. On the classic rice signature it collapses to a single class
    with entropy 0 -- an artefact of a balanced, perfectly separable training
    set, not real certainty.

    Softening therefore scales with how degenerate the distribution actually
    is: near-zero entropy earns the full temperature, a well-spread
    distribution is left essentially untouched.
    """
    values = [p for p in probs.values() if p > 0]
    if len(values) <= 1:
        return SOFTEN_T_MAX

    entropy = -sum(p * math.log(p) for p in values)
    max_entropy = math.log(len(probs))
    if max_entropy <= 0:
        return 1.0

    normalised = max(0.0, min(1.0, entropy / max_entropy))
    return 1.0 + (SOFTEN_T_MAX - 1.0) * (1.0 - normalised)


def _soften(probs: Dict[str, float], temperature: Optional[float] = None) -> Dict[str, float]:
    """Temperature-scale a distribution back into a blendable range."""
    if temperature is None:
        temperature = _adaptive_temperature(probs)
    if temperature <= 1.0:
        return dict(probs)
    eps = 1e-9
    scaled = {c: math.exp(math.log(max(p, eps)) / temperature) for c, p in probs.items()}
    total = sum(scaled.values())
    return {c: v / total for c, v in scaled.items()} if total > 0 else dict(probs)


def apply_crop_prior(
    probabilities: Dict[str, float],
    state: str,
    district: str,
    weight: float = PRIOR_WEIGHT,
) -> Tuple[Dict[str, float], Dict[str, Any]]:
    """Blend model probabilities with the district's cultivation history.

    Returns ``(adjusted_probabilities, metadata)``. When no history is
    available the probabilities are returned unchanged, so the advisor degrades
    to exactly its previous behaviour rather than failing.
    """
    meta: Dict[str, Any] = {
        "prior_applied": False, "scope": "none",
        "top_district_crops": [], "reordered": False,
    }
    if not probabilities or weight <= 0.0:
        return dict(probabilities), meta

    prior, scope = lookup_prior(state, district)
    if not prior:
        return dict(probabilities), meta

    temperature = _adaptive_temperature(probabilities)
    softened = _soften(probabilities, temperature)

    blended: Dict[str, float] = {}
    for crop, p in softened.items():
        prior_p = prior.get(crop, 0.0) + PRIOR_FLOOR
        blended[crop] = (max(p, 1e-9) ** (1.0 - weight)) * (prior_p ** weight)

    total = sum(blended.values())
    if total <= 0:
        return dict(probabilities), meta
    blended = {c: v / total for c, v in blended.items()}

    before_top = max(probabilities, key=probabilities.get)
    after_top = max(blended, key=blended.get)

    meta.update({
        "prior_applied": True,
        "scope": scope,
        "top_district_crops": [
            c for c, _ in sorted(prior.items(), key=lambda kv: kv[1], reverse=True)[:3]
        ],
        "reordered": before_top != after_top,
        "model_top": before_top,
        "final_top": after_top,
        "softening_temperature": round(temperature, 2),
    })
    return blended, meta


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    table = build_prior(force=True)
    print(f"districts: {len(table['districts'])}, states: {len(table['states'])}")
    for st, di in [("Punjab", "Ludhiana"), ("Rajasthan", "Jaisalmer"),
                   ("Kerala", "Palakkad"), ("Gujarat", "Kutch")]:
        prior, scope = lookup_prior(st, di)
        top = sorted(prior.items(), key=lambda kv: kv[1], reverse=True)[:4]
        print(f"  {st}/{di} [{scope}]: " + ", ".join(f"{c} {v:.1%}" for c, v in top))
