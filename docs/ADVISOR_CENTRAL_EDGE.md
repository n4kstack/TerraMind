# TerraMind Advisor — Central + Edge Architecture

Operations and onboarding guide for the two-mode Advisor.
Implements `TerraMind_Advisor_SRD.md` v1.0.

---

## 1. What changed, and what did not

**Changed — how a prediction is served.** Requests are routed to a state's edge
node when one is qualified, and to central otherwise.

**Unchanged — everything a caller can observe.** Input schema, output schema,
field names, nesting, and the legacy flat duplicates are byte-for-byte
identical to pre-refactor behaviour. `run_standard_pipeline()` keeps its
signature. This is enforced by a regression test against a baseline captured
from the running service *before* any refactor code existed
(`tests/baseline/advisor_schema_baseline.json`).

Exactly two modes exist: `central` and `edge`. There is no third mode.

---

## 2. Architecture

```
                        request  (existing schema, has `state`)
                                    │
                            ┌───────▼────────┐
                            │     Router     │   ml/advisor_edge/router.py
                            │  reads `state` │
                            └───┬────────┬───┘
        qualified node ─────────┘        └───────── no node / disabled /
        + confident                                 breaker open / low
              │                                     confidence / edge error
              ▼                                              ▼
   ┌──────────────────────┐                     ┌─────────────────────────┐
   │  EDGE NODE <state>   │                     │     CENTRAL             │
   │                      │                     │                         │
   │  yield_model.pkl     │ ← regional          │  crop / sunlight /      │
   │    trained only on   │   (that state only) │  irr_type / irr_need /  │
   │    this state's rows │                     │  yield                  │
   │                      │                     │                         │
   │  _shared/            │ ← national replicas │  full dataset           │
   │    crop              │   (compressed,      │  most accurate          │
   │    sunlight          │    distilled)       │  universal fallback     │
   │    irrigation_type   │                     │  distillation teacher   │
   │    irrigation_need   │                     │                         │
   └──────────┬───────────┘                     └───────────┬─────────────┘
              └────────────────────┬────────────────────────┘
                                   ▼
                      response  (identical shape, always)
```

### Why four models are replicas, not regional

Only one Advisor dataset carries geography:

| Model | Training data | State column? |
|---|---|---|
| Yield Predictor | `crop_production.csv.xlsx` + `India Agriculture Crop Production.csv` | ✅ 36 states, 730 districts |
| Crop Recommender | `crop_dataset_rebuilt.csv` | ❌ `N,P,K,temperature,humidity,ph,rainfall,label` |
| Sunlight / Irrigation Type / Irrigation Need | `irrigation_prediction.csv` | ❌ `crop,ph,temperature,humidity,rainfall,soil_type,season` |

A per-state model for the latter four is not merely unwise — it is undefined,
because there is no key to partition on. They are therefore compressed
national models distilled from central and **replicated** onto every node.
They are not claimed to be regional. They live at the edge so a request can be
served end-to-end locally, which is what delivers the latency, central-load,
fault-isolation and bandwidth properties in SRD §2.6.

---

## 3. Module map

| File | Role |
|---|---|
| `ml/data_sources.py` | Dataset discovery. Searches `TerraMind_Datasets/`, legacy dirs, `$TERRAMIND_DATA_DIR`. |
| `ml/advisor_edge/features.py` | **One** feature pipeline shared by both modes. |
| `ml/advisor_edge/candidates.py` | RF / XGBoost / LightGBM / CatBoost registry, central and edge configs. |
| `ml/advisor_edge/train_central.py` | Central models: CV bake-off, winner selection, comparison log. |
| `ml/advisor_edge/train_edge.py` | Per-state yield + replicas; distillation, calibration, ≤4% gate. |
| `ml/advisor_edge/registry.py` | Node discovery, enable/disable, health, circuit breaker. |
| `ml/advisor_edge/router.py` | Mode selection, confidence gating, fallback, fallback logging. |
| `ml/advisor_edge/pipeline.py` | Integration seam; assembles the frozen response shape. |
| `ml/advisor_edge/evaluate.py` | Accuracy-gap harness; can demote drifted nodes. |
| `ml/advisor_edge/benchmark.py` | The five edge-computing proofs. |

---

## 4. Runbook

### Full rebuild

```bash
python -m ml.advisor_edge.train_central     # central reference models
python -m ml.advisor_edge.train_edge        # replicas + all eligible states
python -m ml.advisor_edge.evaluate          # accuracy-gap report
python -m ml.advisor_edge.benchmark         # the five proofs
python -m pytest tests/test_advisor_edge.py -v
```

### Onboarding a new state (NFR-5)

Adding a state requires **no change to central's code path**:

```bash
python -m ml.advisor_edge.train_edge --states <state_key>
```

State keys are lowercase with underscores (`uttar_pradesh`, `tamil_nadu`).
The trainer will:

1. Check the state clears `MIN_ROWS_PER_STATE` (500 train rows, 30 test rows).
2. Train all candidates on **only that state's rows**, distilled from central.
3. Fit a local linear calibration.
4. Compute the gap against central *on that state's own holdout*.
5. Write the node only if the gap is within 4%.

The registry discovers the node from its artifacts on next load. Nothing else
is edited.

### Enabling / disabling a node at runtime

```python
from ml.advisor_edge.registry import registry
registry.set_enabled("punjab", False)   # -> that state falls back to central
registry.set_enabled("punjab", True)
```

This writes `backend/artifacts/edge/advisor/edge_registry.json`. No restart.

### Re-checking the accuracy gap on a schedule

```bash
python -m ml.advisor_edge.evaluate --demote
```

Any node that has drifted past the ceiling is disabled and its state reverts to
central. Run this after every retrain.

---

## 5. Routing rules

A request is served from **edge** only when all of these hold:

1. A node exists for the request's `state`.
2. The node is `enabled` in the registry.
3. The node was `promoted` (gap ≤ 4% at training time).
4. Its artifact file is present.
5. Its circuit breaker is closed.
6. The edge crop-classifier confidence ≥ `CONFIDENCE_THRESHOLD` (0.45).

Otherwise the request is served from **central**, transparently, and the reason
is appended to `backend/artifacts/edge/fallback_events.jsonl` — which is the
signal for where more edge training data is needed (FR-4).

### Circuit breaker

Three consecutive edge failures open the breaker for 60 seconds, during which
the state routes to central. The breaker then half-opens and retries. This is
what stops one failing region cascading into central overload.

### Confidence is internal only

The routing confidence signal is never added to the response body (SRD §10).
A test asserts no `mode`, `execution_mode`, `edge_confidence`, `route_decision`,
`routing` or `served_by` key appears in the output.

---

## 6. Two data issues fixed during this work

Both were pre-existing and both materially affected model quality.

**Per-crop outlier clipping.** Production is denominated in mixed units across
the two yield sources — Tonnes for most crops, Nuts for coconut, Bales for
cotton — so the yield scale is crop-dependent by construction. The previous
global 0.995-quantile clip deleted every legitimately high-yield crop
(sugarcane ~54 t/ha, banana ~22 t/ha) while leaving each crop's own bad rows
in place. Clipping is now applied within each crop.

**Categorical features are no longer label-encoded as numeric.** `crop`,
`state`, `district` and `season` are nominal. Feeding raw integer codes to a
gradient booster as numeric invites splits like `district < 173`, which is
meaningless, and unbounded extrapolation on rare combinations. Measured effect
before the fix: central predicted **up to 2493 t/ha and negative yields** for
Mizoram, against an actual range of 0.1–45.2. All four candidates now use
native categorical handling, and predictions are clamped to a physically
plausible range at inference.

---

## 7. Known characteristics

**Central R² is negative for several small states.** A single global model
generalises poorly to atypical low-volume regions. This is the strongest
argument for regional specialisation, and it is why per-state edge models beat
central on those states rather than merely matching it. Report both R² and MAE
when interpreting: R² on a low-variance subset exaggerates modest absolute
errors.

**The crop recommender scores 1.0 on every split, and it is genuine.** Audited
directly: 0 exact duplicates, 0 duplicate feature vectors, and 0 of 1540 test
points have a near-duplicate in train (median NN distance 0.4709). A 1-NN
classifier with no training reaches 0.9844 on the same split. The crop classes
occupy distinct climate envelopes — rice needs 150–300 mm rainfall at 80–95%
humidity, millets 30–60 mm at 30–55% — so the data is separable by
construction and ~100% is the correct answer for it.

The number describes the dataset's difficulty, not the model's sophistication.
Crop-recommender gap figures between central and edge are therefore
uninformative: both models sit on the same ceiling.

**Irrigation type tops out around 0.45 accuracy** on 4 classes, and the
ceiling is in the data rather than the model. Reference points on the same
split: majority-class baseline 0.3035, 1-NN 0.3685, 15-NN 0.4245. No two rows
share a feature vector with conflicting labels, so the labels are not
contradictory — they are only weakly determined by the seven available
features. A tuned model beating ~0.45 by a wide margin on this feature set
would be cause for suspicion, not celebration.

---

## 7a. Measured results

All figures below were produced by the runbook in §4 on 2026-07-30. Nothing is
estimated; regenerate with `evaluate` and `benchmark`.

### Central model selection

Selection is **accuracy-first**: candidates are ranked by CV, the top three are
refit on the FULL training split, and the winner is chosen on holdout score.
Size breaks *exact* ties only (`SELECTION_TOLERANCE = 0.0`) — a smaller model
can never displace a more accurate one.

| Target | Winner | Holdout metric | Size | Runners-up (full refit) |
|---|---|---|---|---|
| crop_recommender | RandomForest | acc 1.0000 | 3.0 MB | CatBoost 1.0000 (9 MB), XGB 0.9987 |
| sunlight | RandomForest | R² 0.9657 | 58 MB | CatBoost 0.9655, XGB 0.9621 |
| irrigation_type | CatBoost | acc 0.4520 | 4.0 MB | XGB 0.4330, RF 0.4115 |
| irrigation_need | CatBoost | acc 0.8145 | 3.2 MB | LGBM 0.7915, XGB 0.7820 |
| yield_predictor | **LightGBM** | **R² 0.7348** | **4.9 MB** | RF 0.7317 (710 MB), CatBoost 0.7256 |

Versus the pre-refactor artifacts: irrigation_type 0.4295 → **0.4520**,
irrigation_need 0.7985 → **0.8145**. The yield model is not comparable to the
old R² 0.8235 — it trains on a different, cleaner target (per-crop clipping,
both sources merged, 566,740 rows).

#### A selection bug worth recording

The first build ranked candidates on 3-fold CV over a 120k-row subsample and
shipped the leader directly. On the yield target that chose RandomForest
(CV 0.7160). Refitting every candidate on all 453k rows and scoring the real
holdout told a different story:

| Algorithm | test R² | test MAE | size | latency |
|---|---|---|---|---|
| LightGBM-XL | 0.7352 | 27.582 | 119.8 MB | 10.4 ms |
| **LightGBM** | **0.7348** | **27.729** | **4.9 MB** | 9.1 ms |
| XGBoost | 0.7335 | 28.003 | 103.0 MB | 8.0 ms |
| XGBoost-XL | 0.7333 | 27.842 | 542.8 MB | 14.6 ms |
| RandomForest | 0.7317 | 27.868 | 710.3 MB | 100.5 ms |
| CatBoost | 0.7256 | 30.248 | 17.5 MB | 3.5 ms |
| CatBoost-XL | 0.6935 | 31.058 | 129.8 MB | 3.1 ms |

RandomForest placed **fifth of seven**. LightGBM is more accurate, 145× smaller
and 11× faster — a strict improvement on every axis, so nothing was traded.
Reproduce with `python -m ml.advisor_edge.yield_shootout`.

Central artifacts total **~73 MB**, down from 779 MB, with accuracy equal or
better on every one of the five targets.

### Accuracy gap — 29/29 within the 4% ceiling

Replicas: crop +0.0000, sunlight +0.0013, irrigation_type −0.0135,
irrigation_need +0.0095.

Per-state yield gaps span −0.1825 (sikkim) to +0.0012 (maharashtra). Negative
means the regional model *beats* central on that state, which is the expected
benefit of specialisation.

**Held on central: `mizoram`** — central R² −1183, edge R² −2.71. The gap test
passes spectacularly, but both models lose to predicting the mean, so the
absolute floor (§ MIN_EDGE_R2) disqualifies it. Mizoram needs a data-quality
investigation, not a model.

**Skipped as sparse:** `chandigarh`, `daman_and_diu`, `delhi`, `laddakh`
(below 500 rows), plus `dadra_and_nagar_haveli` and `goa` (below the train
floor at split time). All six serve from central.

### The five proofs

| # | Proof | Result |
|---|---|---|
| 1 | Latency | p50 **219.5 ms → 40.5 ms** (−81.5%), p95 275.1 → 51.8 ms (−81.2%), **5.42×** |
| 2 | Central load | 200 requests: **200 → 0** central hits (−100%) |
| 3 | Fault isolation | victim edge→central, **7/7** other states unaffected, blast radius contained |
| 4 | Bandwidth | 35,150 B raw, **0 B** to central — 100% kept local |
| 5 | Scalability | disabled→central, enabled→edge; **0** central code changes, no restart |

The latency win is mostly explained by model choice: central keeps RandomForest
where it wins on score (crop 49 ms, sunlight 67 ms, yield 71 ms single-row),
while edge selection breaks score ties toward the faster candidate and lands on
XGBoost at 1–4 ms.

### Footprint

Central totals ~73 MB, the largest single artifact being the sunlight
RandomForest at 58 MB (it is the most accurate on that target, so it stays).
The yield model is 4.9 MB against the pre-refactor 332 MB, at higher accuracy.
Per-state edge yield models are 1–15 MB each; the shared replica set is 4.1 MB
and is identical on every node.

---

## 8. Acceptance criteria status

| # | Criterion | Where verified |
|---|---|---|
| 1 | Exactly two modes | `test_exactly_two_modes`, `test_no_third_mode_in_router` |
| 2 | Schema identical to baseline | `test_response_shape_matches_baseline`, `test_nested_structure_unchanged` |
| 3 | Every active node ≤ 4% gap | `test_no_promoted_node_breaches_ceiling`, `accuracy_gap_report.json` |
| 4 | Unqualified states fall back | `test_unknown_state_falls_back_to_central`, `test_disabled_node_falls_back` |
| 5 | Latency + load reduction measured | `benchmark_report.json` §latency, §central_load |
| 6 | Fault isolation passes | `benchmark_report.json` §fault_isolation |
| 7 | New state = config only | `benchmark_report.json` §scalability |
| 8 | Model selection log exists | `central_metadata.json` → `targets.*.candidates` |

---

## 9. Generated artifacts

```
backend/artifacts/
├── central/advisor/
│   ├── crop_model.pkl, crop_scaler.pkl, crop_label_encoder.pkl
│   ├── irrigation_preprocessor.pkl, sunlight_model.pkl
│   ├── irrigation_type_model.pkl, irrigation_type_encoder.pkl
│   ├── irrigation_need_model.pkl, irrigation_need_encoder.pkl
│   ├── yield_model.pkl, yield_encoders.pkl
│   └── central_metadata.json          ← model comparison log
└── edge/
    ├── advisor/
    │   ├── _shared/                   ← compressed national replicas
    │   ├── <state>/yield_model.pkl    ← regional, one per promoted state
    │   ├── <state>/node_metadata.json
    │   ├── edge_registry.json         ← enable/disable overlay
    │   ├── edge_metadata.json
    │   ├── accuracy_gap_report.json
    │   └── benchmark_report.json
    └── fallback_events.jsonl          ← retraining prioritisation signal
```

`backend/artifacts/` is gitignored. Rebuild with the runbook in §4.
