"""TerraMind Advisor — central + edge two-mode prediction architecture.

Exactly two serving modes exist: ``central`` and ``edge``. See SRD sections 4-5.

Module layout
-------------
``features``    One shared feature-engineering pipeline used by BOTH modes.
``candidates``  Candidate algorithm registry (RF / XGBoost / LightGBM / CatBoost).
``train_central`` Central reference models, trained on the full dataset.
``train_edge``  Per-state yield models + compressed national replicas.
``registry``    Edge-node registry; onboarding a state is a config addition.
``router``      Routing, health checks, confidence gating, central fallback.
``evaluate``    Accuracy-gap harness enforcing the <= 4% promotion ceiling.
``benchmark``   Latency / load / fault-isolation / bandwidth / scalability proofs.
"""

MODE_CENTRAL = "central"
MODE_EDGE = "edge"
MODES = (MODE_CENTRAL, MODE_EDGE)

#: Maximum permitted ``central_metric - edge_metric`` for promotion (SRD FR-7).
ACCURACY_GAP_CEILING = 0.04

__all__ = ["MODE_CENTRAL", "MODE_EDGE", "MODES", "ACCURACY_GAP_CEILING"]
