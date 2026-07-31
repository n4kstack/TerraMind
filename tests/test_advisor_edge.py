"""Tests for the central/edge two-mode Advisor.

Covers the three things the SRD gates acceptance on:

  * schema regression -- the response contract is byte-for-byte unchanged
  * routing           -- a qualified node serves its state from edge
  * fallback          -- everything else transparently serves from central

The schema baseline in ``tests/baseline/advisor_schema_baseline.json`` was
captured from the running service BEFORE any refactor code existed. It is the
ground truth for Acceptance Criterion 2 and must not be regenerated to make a
failing test pass.

Run:
    python -m pytest tests/test_advisor_edge.py -v
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE = PROJECT_ROOT / "tests" / "baseline" / "advisor_schema_baseline.json"

pytestmark = pytest.mark.filterwarnings("ignore")


def _shape(obj):
    """Recursive type skeleton -- compares structure, not values."""
    if isinstance(obj, dict):
        return {k: _shape(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_shape(obj[0])] if obj else []
    return type(obj).__name__


@pytest.fixture(scope="module")
def baseline():
    if not BASELINE.exists():
        pytest.skip(f"baseline missing: {BASELINE}")
    return json.loads(BASELINE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def artifacts_ready():
    from ml.advisor_edge.router import central_artifacts

    if not central_artifacts.ready():
        pytest.skip("central artifacts not trained yet")
    return True


# ═══════════════════════════════════════════════════════════════════════════
# Acceptance Criterion 1 -- exactly two modes
# ═══════════════════════════════════════════════════════════════════════════

def test_exactly_two_modes():
    from ml.advisor_edge import MODES

    assert MODES == ("central", "edge"), f"expected two modes, got {MODES}"
    assert len(MODES) == 2


def test_no_third_mode_in_router():
    """Router may only ever return one of the two declared modes."""
    from ml.advisor_edge import MODES
    from ml.advisor_edge import router as R

    src = Path(R.__file__).read_text(encoding="utf-8")
    for forbidden in ("local_only", "hybrid", "MODE_LOCAL", "MODE_HYBRID"):
        assert forbidden not in src, f"third mode '{forbidden}' present in router"
    assert set(MODES) == {"central", "edge"}


#: Directories that make up the Advisor's serving path, backend and frontend.
_MODE_SCAN_ROOTS = ("ml", "backend", "frontend/src")
_MODE_SCAN_SUFFIXES = (".py", ".js", ".jsx", ".css")
_MODE_SCAN_EXCLUDE = ("__pycache__", "node_modules", "dist", ".venv", "artifacts")
#: Third-mode spellings. `local_adaptation` / `LocalAdaptationService` are NOT
#: listed: those are the edge-mode bounded-adaptation feature, not a mode.
_FORBIDDEN_MODE_TOKENS = ("local_only", "LOCAL_ARTIFACTS", "mode-local", "MODE_LOCAL")


def test_no_third_mode_anywhere_in_repo():
    """Acceptance Criterion 1 -- no third mode in code OR config, repo-wide.

    Scoping this to router.py alone was not enough: `local_only` survived in
    the legacy request schema, the model registry, the benchmark service and
    the frontend's mode selector long after the router itself was clean.
    """
    offenders = []
    for root_name in _MODE_SCAN_ROOTS:
        root = PROJECT_ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in _MODE_SCAN_SUFFIXES:
                continue
            if any(part in _MODE_SCAN_EXCLUDE for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for token in _FORBIDDEN_MODE_TOKENS:
                if token in text:
                    rel = path.relative_to(PROJECT_ROOT)
                    offenders.append(f"{rel}: {token}")

    assert not offenders, (
        "third-mode references found (only 'central' and 'edge' may exist):\n  "
        + "\n  ".join(sorted(offenders))
    )


def test_request_schema_accepts_only_two_modes():
    """The legacy /predict input validator recognises exactly two modes.

    An unrecognised mode is coerced to ``central`` rather than rejected --
    central is the universal fallback (FR-1), so degrading to it is safer than
    failing the request. What matters for Acceptance Criterion 1 is that no
    third mode can ever survive normalisation.
    """
    from backend.utils.normalizers import normalise_input

    base = {"N": 90, "P": 42, "K": 43, "ph": 6.5, "temperature": 21,
            "humidity": 82, "rainfall": 203, "state": "Punjab",
            "district": "Ludhiana", "season": "kharif", "soil_type": "alluvial"}

    for mode in ("central", "edge"):
        assert normalise_input({**base, "mode": mode})["mode"] == mode

    for rejected in ("local_only", "local", "hybrid", "", "garbage"):
        assert normalise_input({**base, "mode": rejected})["mode"] == "central", (
            f"mode '{rejected}' must normalise to central, never survive"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Acceptance Criterion 2 -- schema regression
# ═══════════════════════════════════════════════════════════════════════════

def test_response_shape_matches_baseline(baseline, artifacts_ready):
    """The refactored pipeline must return the pre-refactor structure."""
    from ml.pre_sowing_pipeline import run_standard_pipeline

    for case_name, case in baseline.items():
        result = run_standard_pipeline(case["request"])
        expected_keys = set(case["top_keys"])
        actual_keys = set(result.keys())

        missing = expected_keys - actual_keys
        added = actual_keys - expected_keys
        assert not missing, f"{case_name}: fields REMOVED from response: {missing}"
        assert not added, f"{case_name}: fields ADDED to response: {added}"


def test_nested_structure_unchanged(baseline, artifacts_ready):
    """Nested blocks must keep their key sets."""
    from ml.pre_sowing_pipeline import run_standard_pipeline

    case = baseline["punjab_kharif"]
    result = run_standard_pipeline(case["request"])
    expected = case["response_shape"]

    for block in ("crop_recommender", "yield_predictor",
                  "agri_condition_advisor", "district_intelligence",
                  "input_summary"):
        assert block in result, f"missing block: {block}"
        assert set(result[block].keys()) == set(expected[block].keys()), (
            f"{block}: key set changed\n"
            f"  expected {sorted(expected[block].keys())}\n"
            f"  actual   {sorted(result[block].keys())}"
        )


def test_no_internal_routing_fields_leak(artifacts_ready):
    """Confidence/mode signals are internal (SRD section 10) -- never in the body."""
    from ml.pre_sowing_pipeline import run_standard_pipeline

    result = run_standard_pipeline({
        "N": 90, "P": 42, "K": 43, "ph": 6.5, "temperature": 21,
        "humidity": 82, "rainfall": 203, "state": "Punjab",
        "district": "Ludhiana", "season": "kharif", "soil_type": "alluvial",
    })
    for leaked in ("mode", "execution_mode", "edge_confidence",
                   "route_decision", "routing", "served_by"):
        assert leaked not in result, f"internal routing field leaked: {leaked}"


# ═══════════════════════════════════════════════════════════════════════════
# Routing and fallback
# ═══════════════════════════════════════════════════════════════════════════

def test_unknown_state_falls_back_to_central(artifacts_ready):
    from ml.advisor_edge import router as R

    _, decision = R.route_and_predict({
        "N": 90, "P": 42, "K": 43, "ph": 6.5, "temperature": 21,
        "humidity": 82, "rainfall": 203, "state": "Atlantis",
        "district": "nowhere", "season": "kharif",
    })
    assert decision.mode == "central"
    assert decision.reason == "no_edge_node"
    assert decision.edge_available is False


def test_promoted_state_serves_from_edge(artifacts_ready):
    from ml.advisor_edge import router as R
    from ml.advisor_edge.registry import registry

    states = registry.available_states()
    if not states:
        pytest.skip("no edge nodes trained yet")

    _, decision = R.route_and_predict({
        "N": 90, "P": 42, "K": 43, "ph": 6.5, "temperature": 21,
        "humidity": 82, "rainfall": 203, "state": states[0],
        "district": "", "season": "kharif",
    })
    assert decision.mode == "edge", f"expected edge for {states[0]}, got {decision.reason}"


def test_disabled_node_falls_back(artifacts_ready):
    from ml.advisor_edge import router as R
    from ml.advisor_edge.registry import registry

    states = registry.available_states()
    if not states:
        pytest.skip("no edge nodes trained yet")

    state = states[0]
    registry.set_enabled(state, False)
    try:
        _, decision = R.route_and_predict({
            "N": 90, "P": 42, "K": 43, "ph": 6.5, "temperature": 21,
            "humidity": 82, "rainfall": 203, "state": state,
            "district": "", "season": "kharif",
        })
        assert decision.mode == "central"
    finally:
        registry.set_enabled(state, True)


def test_circuit_breaker_opens_after_threshold():
    from ml.advisor_edge.registry import FAILURE_THRESHOLD, EdgeNode

    node = EdgeNode(state="testland")
    assert node.is_healthy()
    for _ in range(FAILURE_THRESHOLD):
        node.record_failure()
    assert not node.is_healthy(), "breaker should be open"
    assert not node.is_available()


def test_success_resets_failure_count():
    from ml.advisor_edge.registry import EdgeNode

    node = EdgeNode(state="testland")
    node.record_failure()
    node.record_failure()
    node.record_success()
    assert node.consecutive_failures == 0


# ═══════════════════════════════════════════════════════════════════════════
# Accuracy-gap governance
# ═══════════════════════════════════════════════════════════════════════════

def test_no_promoted_node_breaches_ceiling():
    """Acceptance Criterion 3 -- nothing over the ceiling may serve from edge."""
    from ml.advisor_edge import ACCURACY_GAP_CEILING
    from ml.advisor_edge.registry import registry

    registry.load(force=True)
    offenders = [
        (s, n.gap) for s, n in registry.all_nodes().items()
        if n.is_available() and n.gap is not None and n.gap > ACCURACY_GAP_CEILING
    ]
    assert not offenders, (
        f"nodes serving from edge despite breaching the "
        f"{ACCURACY_GAP_CEILING:.0%} ceiling: {offenders}"
    )


def test_shared_pipeline_used_by_both_modes():
    """Central and edge must build features identically (SRD 2.3)."""
    from ml.advisor_edge import features as F

    payload = {"N": 90, "P": 42, "K": 43, "temperature": 21,
               "humidity": 82, "ph": 6.5, "rainfall": 203}
    import pandas as pd

    row = F.engineer_crop_features(pd.DataFrame([payload]))
    for col in F.CROP_ENGINEERED:
        assert col in row.columns, f"engineered feature missing: {col}"
    assert list(row[F.CROP_ALL_FEATURES].columns) == F.CROP_ALL_FEATURES
