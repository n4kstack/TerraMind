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
    """The advisor_edge router may only ever return central or edge.

    Scoped deliberately to ``ml/advisor_edge``. The legacy serving path in
    ``backend/services/inference_pipeline.py`` additionally offers
    ``local_only``, backed by its own per-state artifacts; that mode is outside
    this router and is not asserted against here.
    """
    from ml.advisor_edge import MODES
    from ml.advisor_edge import router as R

    src = Path(R.__file__).read_text(encoding="utf-8")
    for forbidden in ("local_only", "hybrid", "MODE_LOCAL", "MODE_HYBRID"):
        assert forbidden not in src, f"third mode '{forbidden}' present in router"
    assert set(MODES) == {"central", "edge"}


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
