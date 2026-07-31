# TerraMind — Complete Project Reference

**As-built technical reference.** Every statement here was verified against source code or by running the system on 2026-07-30. Where the aspirational `wholeprojectreadme.md` differs from what the code actually does, this document describes the code and flags the difference.

**Scope:** 169 Python files (~21k LOC), 36 JS/JSX files, FastAPI backend, React/Vite frontend, 5 ML subsystems.

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Repository Map](#2-repository-map)
3. [Architecture: The Two API Surfaces](#3-architecture-the-two-api-surfaces)
4. [Request Flows](#4-request-flows)
5. [Subsystem Reference](#5-subsystem-reference)
6. [Models: Actual Measured Performance](#6-models-actual-measured-performance)
7. [Data & Artifacts](#7-data--artifacts)
8. [Configuration](#8-configuration)
9. [Complete API Reference](#9-complete-api-reference)
10. [Frontend](#10-frontend)
11. [Deployment](#11-deployment)
12. [Known Issues](#12-known-issues)
13. [Discrepancies vs. wholeprojectreadme.md](#13-discrepancies-vs-wholeprojectreadmemd)
14. [Appendix: Verified Run Output](#14-appendix-verified-run-output)

---

## 1. Quick Start

### Prerequisites

| Tool | Deployed version | Verified working |
|---|---|---|
| Python | 3.11.11 (`runtime.txt`, Dockerfile) | 3.14.4 |
| Node | 20 (Dockerfile) | 24.14.1 |

Python 3.14 with sklearn 1.8.0 / numpy 2.4.4 / torch 2.11.0 unpickles all saved models without error. You are developing ahead of the deploy target; this works today but is not what ships.

### Install

```bash
pip install -r backend/requirements.txt     # 22 packages incl. torch, faiss-cpu, sentence-transformers
cd frontend && npm ci
```

`federated/requirements.txt` is a **separate, pinned, conflicting** set (torch 2.3.1 vs backend's `torch>=2.2.0`, numpy 1.26.4 vs `numpy>=1.24`). It is only needed to *retrain* the federated model via Flower. Serving the FL model needs nothing beyond the backend set — `federated/inference.py` deliberately avoids importing `flwr`.

### Run

```bash
# Backend — port must match frontend/.env (currently 8011)
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8011

# Frontend
cd frontend && npm run dev        # http://localhost:3000
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend | http://127.0.0.1:8011 |
| Swagger | http://127.0.0.1:8011/docs |

**Port coupling:** `frontend/.env` hardcodes `VITE_API_BASE_URL=http://localhost:8011`. `.env.example` says 8000 and `backend/core/config.py` defaults to 8000. Pick one and keep the two in sync, or the browser silently fails every API call.

**Windows note:** Vite binds `localhost`, which may resolve to `::1`. Probing `127.0.0.1:3000` can fail while `localhost:3000` succeeds.

### Fastest health check

```bash
curl http://127.0.0.1:8011/metadata                    # 200 — legacy surface alive
curl http://127.0.0.1:8011/api/v1/graph-rag/health     # 200 — KG loaded
curl http://127.0.0.1:8011/health                      # 404 — see Known Issues #1
```

---

## 2. Repository Map

```
├── backend/
│   ├── api/                    Legacy routes: /predict /train /sync /benchmark
│   ├── app/                    v1 API — the surface the frontend actually uses
│   │   ├── api/v1/             advisor, monitor, diagnosis, chatbot, graph_rag, architecture
│   │   ├── chatbot/            PDF RAG: ingestion, retrievers, router, generators
│   │   ├── core/               config, rate_limit, runtime_config
│   │   ├── schemas/            Pydantic request/response models
│   │   ├── services/           Service layer + architecture_service
│   │   └── main.py             ★ FastAPI entrypoint, mounts BOTH surfaces
│   ├── artifacts/              central/edge/local models — 161 MB, gitignored, usually absent
│   ├── core/                   config.py (paths, hyperparams), logging_config
│   ├── models/                 Training scripts for the artifacts/ system
│   ├── services/               Second inference pipeline (edge/central/local)
│   └── utils/                  data_loader, cache_builder, naming_maps, normalizers
├── ml/                         ★ The models actually served
│   ├── pre_sowing_advisor/     crop_recommendation, yield_prediction, irrigation_sunlight
│   │                           + district_intelligence.py (768 L), irrigation_prior.py
│   ├── growth_stage_monitor/   5 cascade models
│   ├── post_symptom_diagnosis/ TorchScript CNN wrapper
│   └── pre_sowing_pipeline.py  ★ The live orchestrator
├── graph_rag/                  KG + 10 external source adapters + LLM synthesis
│   ├── retrieval/adapters/     agris, agricola, pubag, cabi, agecon, asabe,
│   │                           faostat, cgiar, climate, soil
│   ├── cache/                  36 cached retrieval JSONs
│   └── agrokg.pkl              MultiDiGraph: 55 nodes, 117 edges, 158 index entries
├── federated/                  Flower FL — AdvisorNet, 28 state clients
│   └── results/                Trained weights + scaler + encoders (committed)
├── meta_learner/inference.py   EnsembleAdvisor — DEAD CODE, nothing imports it
├── frontend/src/               React 18 + Vite 5 + Tailwind
├── routers/graph_rag_router.py Orphaned — not mounted by main.py
├── chatbot/                    README only; source PDFs absent
└── evaluation_graphs/          29 PNGs — SYNTHETIC, see Known Issues #6
```

**Directories that are not what their name suggests:**

- `chatbot/` — contains only `README.md`. The chatbot *code* lives in `backend/app/chatbot/`. This directory is the configured `TERRAMIND_PDF_FOLDER` source, and its PDFs are not in the repo.
- `graph rag source/` — one file, unused by runtime.
- `backend/graph_rag/` — one file (`agrokg.pkl`), a duplicate of the root copy.
- `routers/` — an orphaned router never mounted.

---

## 3. Architecture: The Two API Surfaces

**This is the single most important thing to understand about this codebase.** `backend/app/main.py` mounts two complete, independent implementations of the pre-sowing advisor.

```
                        backend/app/main.py
                                │
          ┌─────────────────────┴─────────────────────┐
          │                                           │
   LEGACY SURFACE                              V1 SURFACE
   (backend/api/)                              (backend/app/api/v1/)
          │                                           │
   /predict  /train/*                    /api/v1/advisor  /monitor
   /sync/*   /benchmark/*                /diagnosis  /chatbot
          │                              /graph-rag  /architecture
          ▼                                           │
   backend/services/                                  ▼
   inference_pipeline.py                     ml/pre_sowing_pipeline.py
   (261 L, InferencePipeline)                (241 L, run_standard_pipeline)
          │                                           │
          ▼                                           ▼
   backend/artifacts/                        ml/**/saved_models/
   central | edge | local                    (committed via Git LFS)
   161 MB — GITIGNORED
          │
          └──► absent on fresh clone ──► falls back to run_standard_pipeline
                                          (routes_predict.py:_fallback_predict)
```

### What this means in practice

- **The v1 surface is the real one.** The frontend uses it for every feature. It reads `ml/**/saved_models/`, which *are* committed.
- **The legacy surface is a fallback shell.** `backend/artifacts/` is gitignored, so on any fresh clone `/predict` catches `FileNotFoundError` and delegates to the same `run_standard_pipeline` the v1 surface uses. The edge/central/local distinction, local adaptation, and sync/benchmark machinery are inert unless you generate artifacts locally.
- **Four modules exist twice**, with different implementations:

| Concern | v1 / `ml/` | Legacy / `backend/` |
|---|---|---|
| District intelligence | `ml/pre_sowing_advisor/district_intelligence.py` (768 L) | `backend/services/district_intelligence.py` (162 L) |
| Irrigation prior | `ml/pre_sowing_advisor/irrigation_prior.py` (111 L) | `backend/services/irrigation_prior.py` (137 L) |
| Normalizers | `ml/pre_sowing_advisor/normalizers.py` (157 L) | `backend/utils/normalizers.py` (43 L) |
| Pipeline | `ml/pre_sowing_pipeline.py` (241 L) | `backend/services/inference_pipeline.py` (261 L) |

The frontend straddles both: [`advisorService.js`](frontend/src/services/advisorService.js) calls v1, while [`api.js`](frontend/src/services/api.js) calls legacy `/predict`, `/metadata`, `/sync/status`, `/benchmark/*`. [`Advisor.jsx`](frontend/src/pages/Advisor.jsx) imports from both.

### Dual import paths

Modules under `backend/app/` are imported two different ways, sometimes in the same file:

```python
# backend/app/services/diagnosis_service.py:18-19
from backend.app.core.runtime_config import DIAGNOSIS_REPORT_TTL_SECONDS   # package-absolute
from app.schemas.diagnosis import DiagnosisResponse, TopPrediction         # backend/ on sys.path
```

29 files under `backend/app/chatbot/` use the bare `app.*` form. This resolves only because:
- `main.py:16-18` inserts both `PROJECT_ROOT` and `PROJECT_ROOT/backend` into `sys.path`
- the Dockerfile sets `PYTHONPATH=/app/backend`

**Risk:** any module imported under both spellings becomes two distinct objects in `sys.modules` with independent state. Currently benign — the gating state (`report_store`, `downloaded_reports`) is consistently reached via `backend.app.services.diagnosis_service`. Adding an `app.services.diagnosis_service` import anywhere would silently split the chatbot gate into two disconnected sets.

---

## 4. Request Flows

### 4.1 Pre-Sowing Advisory

`POST /api/v1/advisor/predict` → [`advisor.py:64`](backend/app/api/v1/advisor.py#L64) → branches on `model_mode`.

**Standard path** (`ml/pre_sowing_pipeline.py:run_standard_pipeline`), 6 sequential steps:

```
input {N,P,K,ph,temperature,humidity,rainfall,soil_type,state,district,season}
  │
  1. predict_crop()          RandomForestClassifier + engineered features
  │                          → selected_crop, top_3, selected_confidence
  │                          ✗ FAILURE = FATAL (raises RuntimeError)
  2. predict_yield()         RF on (crop, state, district, season)
  │                          → expected_yield, confidence_band (±residual_std)
  │                          ✓ degrades to 0.0 + explanation
  3. predict_irrigation_advisory()   3 models: sunlight / irr_type / irr_need
  │                          ✓ degrades to sprinkler/medium/6.0h
  4. get_district_intelligence()     ICRISAT lookups → 7 insights
  │                          ✓ degrades to "unavailable" stub
  5. apply_irrigation_prior()        Overrides irr_type from district data
  │                          ✓ degrades to prior_used=False
  6. Assemble response
```

Only step 2 depends on step 1's output. Steps 3–5 are independent of the crop except as a feature. **Only the crop recommender is fatal** — everything else degrades gracefully with a `system_notes` entry.

The response carries both a nested structure (`crop_recommender`, `yield_predictor`, `agri_condition_advisor`, `district_intelligence`) and **flat legacy duplicates** (`recommended_crop`, `predicted_yield`, `sunlight_hours`, `confidence`, …) at lines 229-237. Both are populated on every call.

**Federated path** (`model_mode: "federated"`) returns a **completely different, incompatible shape** — flat `predicted_crop` / `top_3_predictions` / `yield_estimate_tons_per_hectare`, with no irrigation, sunlight, or district intelligence. See §5.4.

### 4.2 Growth Stage Monitor

`POST /api/v1/monitor/predict` → `growth_stage_service.run_growth_stage_pipeline`.

Cascade architecture — earlier predictions become features for later ones:

```
X = [temperature, humidity, moisture, soil_type, crop_type, N, P, K, ph, rainfall]
  │
  ├─ pest_level         RandomForestClassifier      → y_pest
  │                     X' = X ⊕ y_pest
  ├─ recommended_fertilizer  RandomForestClassifier → y_fert
  │                     X'' = X ⊕ y_pest ⊕ y_fert
  ├─ dosage                       GradientBoostingRegressor
  ├─ apply_after_days             GradientBoostingRegressor
  └─ expected_yield_after_dosage  GradientBoostingRegressor
```

**Critical:** `pest_level` scores 0.3335 validation accuracy on 3 classes — exactly chance (§6). Because of the cascade, that noise is injected as a feature into all three regressors. The cascade amplifies the weakest link rather than isolating it.

### 4.3 Disease Diagnosis → Gated Chatbot

The only stateful, multi-step flow in the system:

```
1. POST /api/v1/diagnosis/predict  (multipart image)
   └─ ml/post_symptom_diagnosis: PIL decode → 192px → ImageNet norm
      → TorchScript forward → softmax → topk(3)
      → returns {identified_crop, identified_class, confidence,
                 top_k_predictions, report_id}
   └─ report_store[report_id] = None          # sentinel: generating
   └─ BackgroundTask: run_report_generation() → graph_rag LLM

2. GET /api/v1/diagnosis/report/{report_id}
   └─ {"status": "processing"} until the LLM returns

3. POST /api/v1/diagnosis/report/{report_id}/download
   └─ downloaded_reports.add(report_id)       # ← THE GATE OPENS HERE

4. POST /api/v1/chatbot/ask  {question, report_id}
   └─ chatbot.py:52 — if report_id not in downloaded_reports → REJECT
```

**State is process-local**: `report_store` is a plain `dict`, `downloaded_reports` a plain `set`, both module-level in `diagnosis_service.py`. Cleanup is `loop.call_later(DIAGNOSIS_REPORT_TTL_SECONDS, ...)` — default 1800 s. Consequences: gate resets on restart; breaks entirely with `--workers > 1` (a report downloaded on worker A is invisible to worker B).

### 4.4 Chatbot Retrieval Routing

`backend/app/chatbot/router/orchestrator.py` — `IntelligentOrchestrator.ask()`:

```
query → classify_intent()          LLM-based classifier
          │                        ↓ on LLM failure: rule-based fallback
          ├─ PDF_RAG     → FAISSRetriever      (8,327 chunks)
          ├─ GRAPH_RAG   → GraphRetriever      (agrokg.pkl)
          │                 └─ if nodes_found == 0 → fall back to PDF_RAG
          └─ HYBRID_RAG  → HybridRetriever     (both, merged)
                            ↓
                     compose_answer()  → LLM
                            ↓ on LLM failure
              "I could not reach the language model right now,
               but here is the relevant information I found: …"
               + raw KG + PDF context
```

Every routing decision is appended as JSON to **`error.log`** (`orchestrator.py:71`) — a deliberate choice noted in-code as a stand-in for an ELK stack. This is why `error.log` contains structured decision records interleaved with stack traces.

### 4.5 Graph RAG Query

`POST /api/v1/graph-rag/query` → `graph_rag/graph_rag_pipeline.py:GraphRAGPipeline.run()`:

```
query → IntentParser → ParsedIntent {crop, pest, disease, climate, soil}
  │
  ├─ _is_agriculture_query()?  16 domain regexes + crop/pest lexicon
  │     └─ NO → _generate_general_response()  (skips retrieval entirely)
  │
  ├─ KG query          → graph context text
  ├─ _build_external_context()   parallel fan-out to 10 adapters
  │     └─ grounding_policy: metadata-only hits → conservative_mode,
  │        answer suppressed rather than hallucinated
  │
  ├─ _build_prompt()   → strict 5-section output contract
  ├─ _generate_with_ollama()  → OpenRouter (name is legacy)
  │     ├─ _post_with_retry()
  │     ├─ _try_fallback_model()      GRAPH_RAG_FALLBACK_MODEL
  │     └─ GRAPH_RAG_MODEL_CANDIDATES (ordered list)
  │
  └─ _is_incomplete_response()?  checks all 5 sections + sentence termination
        ├─ retry with +400 tokens
        └─ _append_minimum_completion()  if still truncated
```

The 5-section contract: (1) Identified High-Risk Pests/Diseases, (2) Weather-Disease Link, (3) AGRIS Evidence, (4) Explicit limitation statement if AGRIS insufficient, (5) Actionable Recommendations.

---

## 5. Subsystem Reference

### 5.1 Crop Recommender

`ml/pre_sowing_advisor/crop_recommendation/`

- **Model:** `RandomForestClassifier` (a `GradientBoostingClassifier` is trained alongside; the better validation score is kept)
- **Base features:** N, P, K, temperature, humidity, ph, rainfall
- **Engineered:** `NP_ratio`, `KP_ratio`, `rainfall_humidity` — visible in the stored feature importances
- **Classes (10):** barley, cotton, groundnut, maize, millets, pulses, rice, sugarcane, tobacco, wheat
- **Artifacts:** `model.pkl` (5.3 MB), `scaler.pkl`, `label_encoder.pkl`, `metadata.json`
- **Failure mode:** fatal — the only step that aborts the whole pipeline

Feature importances (from `metadata.json`): K 0.183, humidity 0.172, N 0.167, P 0.133, NP_ratio 0.094, rainfall 0.083, rainfall_humidity 0.072, KP_ratio 0.051, temperature 0.036, ph 0.008.

### 5.2 Yield Predictor

`ml/pre_sowing_advisor/yield_prediction/`

- **Model:** `RandomForestRegressor` — *not* XGBoost (`metadata.json: "model_type": "RandomForest"`)
- **Features:** only 4, all categorical — crop, state, district, season. No soil chemistry, no weather.
- **Confidence band:** `residual_std = 0.6089`, `confidence_multiplier = 1.5` → ±0.91 t/ha
- **Artifact:** `model.pkl` — **332 MB**, the single largest file in the repo

With 4 high-cardinality categoricals and no regularisation, this forest is effectively memorising district×crop×season mean yields. That is a legitimate strategy for this problem, but it is a lookup table with 332 MB of overhead, not a learned model. `inference_pipeline.py:199-200` reads optional `residual_q10`/`residual_q90` keys that the `ml/` metadata does not contain, so it falls back to symmetric ±`residual_std`.

### 5.3 Agri-Condition Advisor

`ml/pre_sowing_advisor/irrigation_sunlight/` — three models on one shared preprocessor.

| Target | Model | Output |
|---|---|---|
| `sunlight_hours` | GradientBoostingRegressor | float, clipped [3, 12] |
| `irrigation_type` | GradientBoosting**Classifier** | canal / drip / rainfed / sprinkler |
| `irrigation_need` | GradientBoosting**Classifier** | low / medium / high |

**`irrigation_need` is a classifier, not a regressor.** It returns a categorical label, confirmed by `metadata.json` reporting `irr_need_test_acc` and by `inference_pipeline.py:230` calling `le_irrigation_need.inverse_transform()`. Any code doing arithmetic on it will fail — including the dead `meta_learner` blend (§5.5).

Engineered features: `temp_rainfall_ratio`, `humidity_rainfall`, `rainfall_log`, `temp_humidity_interaction`.

### 5.4 Federated Learning — AdvisorNet

`federated/` — real Flower implementation, **reachable only via the API, never from the UI**.

**Architecture** (`federated/model.py`):

```
Input (7)  → Linear(7→128)  → BatchNorm → ReLU → Dropout(0.2)
           → Linear(128→64) → BatchNorm → ReLU → Dropout(0.2)
           → Linear(64→32)  → BatchNorm → ReLU
                    │ shared 32-dim representation
     ┌──────────┬───┴──────┬──────────────┬──────────────┐
  crop_head  yield_head  sunlight_head  irr_type_head  irr_need_head
   (11 cls)   (1 reg)    (1, clamp 3-12)  (3 cls)     (1, clamp 0-20)
```

Xavier uniform init on Linear layers, zero biases. `forward()` returns all 5 tensors.

**`inference.py:176-177` uses only `outputs[0]` and `outputs[1]`.** `sunlight_pred`, `irrigation_type_logits`, and `irrigation_needed_pred` are computed on every forward pass and discarded. At serving time this is a 2-head network; the clamping at `model.py:92-93` is dead weight.

**Training** (`federated/run_simulation.py`): `data_partitioner.py` shards data into 28 state-level non-IID clients; Flower server runs FedAvg. Flags: `--iid`, `--dp` (Opacus epsilon tracking), `--rounds N`.

**Serving:** `FederatedAdvisor` loads `.pth` + scaler + encoders directly, no `flwr` import — fast cold start.

**Two data problems:**

1. **The FL label encoder has 11 classes to the RF's 10.** The extra class is `paddy`, alongside `rice` — the same crop listed twice. The synonym merge that ran for the RF dataset did not run for the FL partitioner. Live output shows the split: `rice 0.9713, paddy 0.0213`. Any RF↔FL comparison is across mismatched vocabularies.

2. **`accuracy_gap_pct: -0.336`** — the federated model *beat* the centralized baseline (0.9703 vs 0.9671) after 5 non-IID rounds. FedAvg does not normally outperform pooled training. This suggests eval/train overlap or an undertrained baseline, which makes the headline privacy-vs-accuracy claim unsupported.

**Path fragility:** `WEIGHTS_PATH = "federated/results/..."` (`inference.py:20-23`) is relative to **CWD**, not to the module. Launch uvicorn from anywhere but the repo root and `is_available()` returns False, producing a misleading "run the FL simulation first" 503 despite the artifacts being committed and valid.

### 5.5 Meta-Learner — Dead Code

`meta_learner/inference.py` (25 KB, `EnsembleAdvisor`).

**Nothing imports it.** The only repo-wide reference is the string `"meta_learner"` in `architecture_service.py:38`'s directory scan list. It is the only code that would run the RF stack and AdvisorNet together, so the three-strategy voting engine described in the README **never executes in any configuration, API included**.

Designed behaviour (for reference only): Strategy A simple voting, Strategy B weighted `RF×0.6 + FL×0.4`, Strategy C confidence gating at 85%; final answer by majority vote, tiebreak to B. Note it blends `irrigation_need` numerically — which would raise on the categorical the real model returns (§5.3).

### 5.6 Plant Disease CNN

`ml/post_symptom_diagnosis/`

- **Format:** TorchScript (`plant_disease_model_fast_torchscript.pt`) — no architecture code needed at inference
- **Classes:** 88, spanning 25 crops (Apple, Cassava, Cherry, Chili, Coffee, Corn, Cucumber, Gauva, Grape, Jamun, Lemon, Mango, Peach, Pepper_bell, Pomegranate, Potato, Rice, Soybean, Strawberry, Sugarcane, Tea, Tomato, Wheat …)
- **Input:** 192×192, ImageNet normalisation
- **Metadata:** `class_metadata_fast.json` → `class_names`, `class_to_crop`, `num_classes`, `img_size`
- **Import is lazy** (`diagnosis_service.py:62`) so the API boots without torch installed

**No held-out accuracy metric is stored anywhere** for this model. The `~96%` figure in the README has no artifact backing it.

### 5.7 Graph RAG

`graph_rag/` — the most carefully engineered subsystem in the project.

**Knowledge graph:** `agrokg.pkl` = `{"graph": MultiDiGraph(55 nodes, 117 edges), "node_index": dict(158)}`. Built from `kg_data.py` (43 KB curated static knowledge) via `graph_builder.py`. Encodes Crop→Pest, Crop→Disease, Disease→Treatment, Pest→Treatment, Pesticide×Soil conflicts, Pest×Climate risk multipliers, and tank-mix conflicts.

**Retrieval layer** (`graph_rag/retrieval/`) — clean separation of concerns:

| Module | Role |
|---|---|
| `adapters/` (10) | agris, agricola, pubag, cabi, agecon, asabe, faostat, cgiar, climate, soil — all behind `adapters/base.py` |
| `orchestrator.py` | Parallel fan-out |
| `normalizer.py` | Heterogeneous results → common schema |
| `reranker.py` | Relevance ordering |
| `grounding_policy.py` | **Refuses to answer** when hits are metadata-only |
| `context_builder.py` | Prompt context assembly |
| `structured_logger.py` | Retrieval telemetry |

`grounding_policy.py` is the real anti-hallucination mechanism: insufficient document content triggers `conservative_mode` and suppresses generation rather than letting the LLM invent citations.

**Cache:** 36 JSONs in `graph_rag/cache/`, keyed `{crop}__{disease}_{source}.json`.

### 5.8 PDF Chatbot

`backend/app/chatbot/`

- **Index:** FAISS, **8,327 chunks** — `faiss_index.bin` (12.8 MB) + `chunk_metadata.json` (4.9 MB), both committed
- **Embeddings:** `all-MiniLM-L6-v2` via sentence-transformers
- **Loading is lazy.** `GET /api/v1/chatbot/status` reports `index_loaded: false` until something triggers `ensure_loaded()`. This is **not a fault** — a forced load completes in 0.6 s and yields 8,327 chunks.
- **Rebuild** (`POST /api/v1/chatbot/rebuild`) requires source PDFs in `TERRAMIND_PDF_FOLDER` (`chatbot/`), which are **not in the repo**. Commit `28b502c` added a guard for exactly this.

### 5.9 Architecture Service

`backend/app/services/architecture_service.py` (25 KB) — scans source files to auto-generate the architecture graph served at `/api/v1/architecture/snapshot` and rendered by `ArchitectureDiagram.jsx`. Extracts modules, imports, API boundaries, and execution paths rather than relying on a hand-maintained diagram. Layer colours: ui `#38bdf8`, business `#22c55e`, data `#f59e0b`, external `#94a3b8`.

---

## 6. Models: Actual Measured Performance

**Source: the `metadata.json` / `evaluation_summary.json` files written by the training code itself.** Not the README, not the charts.

### Pre-Sowing

| Model | Metric | Value | Assessment |
|---|---|---|---|
| Crop Recommender (RF) | train / val / test acc | **1.0 / 1.0 / 1.0** | ✓ genuine (see below) |
| Crop Recommender (RF) | top-3 acc | 1.0 | ✓ |
| Crop Recommender (GB) | val acc | 0.9987 | ✓ |
| Yield Predictor | test R² | 0.8235 | ✓ plausible |
| Yield Predictor | test MAE / RMSE | 0.3749 / 0.6701 t/ha | ✓ |
| Sunlight | test R² | 0.9662 | ✓ |
| **Irrigation Type** | **test acc** | **0.4295** | ✗ weak |
| Irrigation Need | test acc | 0.7985 | ~ |

### Growth Stage — every value from `evaluation_summary.json`

| Target | Train | Val | Self-reported health |
|---|---|---|---|
| **pest_level** | 0.9488 | **0.3335** | `"OVERFIT"` |
| recommended_fertilizer | 1.0 | **1.0** | `"HEALTHY"` (not audited) |
| dosage | R² 0.9980 | R² 0.9448 | `"HEALTHY"` |
| apply_after_days | R² 0.9621 | R² 0.6987 | `"OVERFIT"` |
| expected_yield_after_dosage | R² 0.9313 | **R² 0.4026** | `"OVERFIT"` |

### Federated

| Metric | Value |
|---|---|
| centralized_accuracy | 0.9671 |
| federated_accuracy | 0.970349 |
| accuracy_gap_pct | **−0.336** (FL ahead — see §5.4) |
| centralized / federated yield MAE | 0.6606 / 0.7087 |
| rounds / clients | **5** / 28 |
| communication cost | 15.36 MB |

### Disease CNN

No stored held-out metric. Live inference on `sample_leaf.jpg` → `Rice__hispa` @ 0.9132.

### How to read these numbers

**`pest_level` at 0.3335 on 3 classes is chance.** The model has learned nothing generalisable, and the cascade (§4.2) feeds it into three downstream regressors.

**The crop recommender's 1.0 is genuine, not leakage.** An earlier revision of
this document called it a leakage signature. That was wrong, and a direct audit
of `crop_dataset_rebuilt.csv` disproves it:

| Check | Result |
|---|---|
| Exact duplicate rows | **0** |
| Duplicate feature vectors (ignoring label) | **0** |
| Test points with a near-duplicate in train (NN distance < 0.01) | **0 / 1540** |
| Median nearest-neighbour distance, test → train | **0.4709** |
| 1-NN accuracy (no training, no tuning) | **0.9844** |

There is no train/test contamination. The dataset is simply separable by
construction — each crop occupies a distinct, tightly bounded climate envelope:

| Crop | rainfall | humidity | temperature |
|---|---|---|---|
| rice | 150–300 | 80–95 | 20–32 |
| wheat | 50–100 | 30–50 | 10–24 |
| barley | 50–100 | 40–60 | 12–25 |
| cotton | 80–140 | 50–70 | 24–35 |
| millets | 30–60 | 30–55 | 26–35 |

A nearest-neighbour classifier reaching 98.4% with no model at all is the
decisive evidence: the classes are nearly linearly separable, so a tuned
RandomForest reaching ~100% is the correct answer for this data, not
overfitting. Treat the score as a statement about the dataset's difficulty
rather than about the model's sophistication.

**`irrigation_type` at 0.4295** is served to users as a recommendation. Live example: Punjab / Ludhiana / kharif / rice returned `rainfed` — Punjab rice is overwhelmingly tube-well irrigated.

---

## 7. Data & Artifacts

### Training datasets — ABSENT

`backend/core/config.py:14` sets `DATASET_DIR = PROJECT_ROOT / "dataset before sowing"`. **That directory does not exist, and no `.csv` or `.xlsx` exists anywhere in the repo.**

Missing: `crop_dataset_rebuilt.csv`, `irrigation_prediction.csv`, `India Agriculture Crop Production.csv`, `crop_production.csv.xlsx`, `ICRISAT-District Level Data.csv`, `ICRISAT-District Level Data Source.csv`, `ICRISAT-District Level Data Irrigation.csv`, `fertilizer_giant_training_dataset.csv`, PlantVillage images.

**Consequences:**
- `POST /api/v1/advisor/train/all` and every `train.py` fail on a fresh clone
- District Intelligence throws `KeyError: 'state'` on **every** request, caught at `district_intelligence.py:755` and returned as the "unavailable" stub — all 7 insights null

### Model artifacts — committed

Git LFS is configured (`.gitattributes`) for `*.pkl *.pt *.pth *.onnx *.joblib *.pdf *.bin`.

| File | Size |
|---|---|
| `ml/.../yield_prediction/saved_models/model.pkl` | **332 MB** |
| `ml/growth_stage_monitor/saved_models/pest_level_model.pkl` | 13.0 MB |
| `backend/app/chatbot/storage/faiss_index.bin` | 12.8 MB |
| `ml/.../irrigation_sunlight/saved_models/model_irrigation_type.pkl` | 11.3 MB |
| `ml/growth_stage_monitor/saved_models/recommended_fertilizer_model.pkl` | 10.8 MB |
| `backend/app/chatbot/storage/chunk_metadata.json` | 4.9 MB |

**`.git` is 896 MB.** Every retrain rewrites the 332 MB blob into history.

`backend/artifacts/` (161 MB, gitignored) exists only if you generate it locally.

### Files that should not be tracked

`error.log` (UTF-16, mixes structured routing logs with stack traces), `training_output.txt` (86 KB), `train_log.txt`, `error_full.txt`, `test.txt` (empty), `python_paths.txt`, `python_path_check.txt`, `visualize_output.txt`.

---

## 8. Configuration

### Backend `.env` (gitignored; template in `.env.example`)

| Variable | Default | Notes |
|---|---|---|
| `TERRAMIND_HOST` / `TERRAMIND_PORT` | `0.0.0.0` / `8000` | Frontend expects **8011** |
| `OPENROUTER_API_KEY` | — | Required for all LLM features |
| `OPENROUTER_MODEL_NAME` | `z-ai/glm-4.5-air:free` | **Retired slug — see Known Issues #2** |
| `GRAPH_RAG_MODEL` | ↑ | |
| `GRAPH_RAG_FALLBACK_MODEL` | ↑ | |
| `GRAPH_RAG_MODEL_CANDIDATES` | ↑ | Comma-separated, ordered |
| `GRAPH_RAG_ENABLE_EXTERNAL_SOURCES` | `true` | |
| `GRAPH_RAG_EXTERNAL_TOP_K` | `4` | |
| `GRAPH_RAG_LLM_MAX_TOKENS` | `1200` | Retry uses `1600` |
| `TERRAMIND_PDF_FOLDER` | `chatbot` | PDFs absent |
| `TERRAMIND_VECTOR_STORE_DIR` | `backend/app/chatbot/storage` | |
| `TERRAMIND_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | |
| `TERRAMIND_CHUNK_SIZE` / `_OVERLAP` | `500` / `50` | |
| `TERRAMIND_TOP_K` | `5` | |
| `TERRAMIND_SIM_THRESHOLD` | `0.35` | |
| `TERRAMIND_DIAGNOSIS_REPORT_TTL_SECONDS` | `1800` | Gate + report lifetime |
| `TERRAMIND_DIAGNOSIS_ALLOWED_CONTENT_TYPES` | jpeg, png, webp, jpg | |

Rate limits via slowapi: API 10/min, advisor predict 15/min, advisor train 2/min, monitor 15/min, chatbot ask 10/min, chatbot rebuild 5/min, diagnosis 10/min.

**All four model variables currently hold the same retired slug**, so the fallback chain provides zero resilience.

### Frontend `frontend/.env`

| Variable | Current | `.env.example` |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8011` | `http://localhost:8000` |
| `VITE_MONITOR_TIMEOUT_MS` | — | `30000` |
| `VITE_DIAGNOSIS_DEFAULT_TOP_K` | — | `3` |

`runtimeConfig.js` derives `API_V1_BASE_URL = ${API_BASE_URL}/api/v1`.

---

## 9. Complete API Reference

Status column reflects live probes against a running instance with `frontend/dist` present.

### v1 surface — used by the frontend

| Method | Path | Status | Purpose |
|---|---|---|---|
| POST | `/api/v1/advisor/predict` | 200 | Full advisory; `model_mode: standard\|federated` |
| POST | `/api/v1/advisor/train/all` | — | Retrain 3 models (fails: no datasets) |
| GET | `/api/v1/advisor/metadata` | 200 | Model metadata |
| POST | `/api/v1/advisor/compare` | — | Legacy compat |
| POST | `/api/v1/monitor/predict` | 200 | Growth stage, 5 outputs |
| POST | `/api/v1/diagnosis/predict?top_k=N` | 200 | Image upload → disease |
| GET | `/api/v1/diagnosis/report/{id}` | 200 | Poll report status |
| POST | `/api/v1/diagnosis/report/{id}/download` | 200 | **Opens the chatbot gate** |
| POST | `/api/v1/chatbot/ask` | 200 | Gated — requires downloaded `report_id` |
| GET | `/api/v1/chatbot/status` | 200 | `index_loaded` is lazy, not health |
| POST | `/api/v1/chatbot/rebuild` | — | Needs source PDFs |
| POST | `/api/v1/graph-rag/query` | 200 | KG + external evidence Q&A |
| GET | `/api/v1/graph-rag/health` | 200 | `{status, provider, model, kg_nodes}` |
| GET | `/api/v1/architecture/snapshot` | 200 | Auto-generated architecture graph |

### Legacy surface

| Method | Path | Status | Purpose |
|---|---|---|---|
| POST | `/predict` | 200 | Edge/central advisory (falls back to standard) |
| GET | `/metadata` | 200 | Model versions |
| GET | `/sync/status` | 200 | Edge↔central sync state |
| POST | `/sync/pull` | — | Pull central → edge |
| POST | `/train/all`, `/train/crop-recommender`, `/train/yield-predictor`, `/train/agri-advisor` | — | Training |
| GET | `/benchmark/results` | 200 | Edge vs central comparison |
| POST | `/benchmark/all`, `/benchmark/edge-assets` | — | Run benchmarks |

### Unreachable at runtime — registered but shadowed

| Method | Path | Status |
|---|---|---|
| GET | `/health` | **404** |
| GET | `/api/states` | **404** |
| GET | `/api/districts/{state}` | **404** |

These appear in `/openapi.json` but 404 in practice. See Known Issues #1.

---

## 10. Frontend

React 18 + Vite 5 + TailwindCSS. Dev server port 3000; preview 4173.

```
src/
├── App.jsx, main.jsx, index.css
├── components/
│   ├── Layout.jsx, Navbar.jsx, PredictionForm.jsx, ResultsDashboard.jsx
│   ├── GraphRAGChat.jsx
│   ├── architecture/ArchitectureDiagram.jsx
│   ├── assistant/SmartAssistantDrawer.jsx
│   ├── forms/       BeforeSowingForm, GrowthStageForm, ImageUploadForm, ChatbotForm
│   └── results/     BeforeSowingResultCard, GrowthStageResultCard,
│                    DiagnosisResultCard, ChatMessageCard, SourceCitationCard
├── pages/           Advisor, Monitor, Diagnosis, Chatbot, GraphRAG, Architecture
├── services/        advisorService, monitorService, diagnosisService,
│                    chatbotService, graphRagService, architectureService, api
├── config/runtimeConfig.js
├── data/state_district_mapping.json      ← local fallback for the dropdowns
└── utils/generateReport.js               ← client-side PDF
```

**Notes:**

- `services/api.js` targets the **legacy** surface; the other five target v1. `Advisor.jsx` imports from both.
- `PredictionForm.jsx` calls `fetchStates`/`fetchDistricts` → `/api/states`, `/api/districts/{state}` — **both 404** (Known Issues #1). A local `state_district_mapping.json` exists and is the natural fix.
- **No component references `model_mode`.** The federated path is unreachable from the UI, and its response shape would not render in `BeforeSowingResultCard` anyway (§5.4).

---

## 11. Deployment

**Target:** Hugging Face Spaces (Docker). No `render.yaml` despite README references.

Two-stage `Dockerfile`:

```dockerfile
FROM node:20-alpine AS frontend-builder   # npm ci && npm run build
FROM python:3.11-slim
ENV PORT=7860 TERRAMIND_PORT=7860 PYTHONPATH=/app/backend
RUN apt-get install -y libgomp1           # OpenMP for sklearn/xgboost
COPY backend/requirements.txt ...
COPY . .
COPY --from=frontend-builder /frontend/dist /app/frontend/dist
CMD uvicorn backend.app.main:app --host 0.0.0.0 --port 7860 --loop asyncio
```

Single container serves API + SPA. `main.py:77-109` mounts `/assets` and adds an SPA catch-all when `frontend/dist` exists.

**Because the Dockerfile always produces `frontend/dist`, the route-shadowing bug is always active in production** — including on `/health`, which is the natural container healthcheck.

`--loop asyncio` is explicit (avoids uvloop). `.dockerignore` excludes `.git`, `node_modules`, logs, caches.

---

## 12. Known Issues

### 1. Route shadowing — `/health` and state dropdowns are dead ✗ HIGH

`main.py` registers the SPA catch-all `@app.get("/{full_path:path}")` at **line 87**, before `/health` (113), `/api/states` (118), `/api/districts/{state}` (132). FastAPI matches in registration order, so the catch-all wins; because those prefixes are in its `passthrough_prefixes` list it raises 404.

Triggers whenever `frontend/dist` exists — true in every Docker deploy.

**Impact:** container healthcheck endpoint dead; Advisor form's state/district dropdowns empty in the browser.

**Fix:** move the SPA block (lines 76-109) *below* the endpoint definitions.

### 2. OpenRouter model slug retired ✗ HIGH

```
HTTP 404: "This model is unavailable for free. The paid version is
available now - use this slug instead: z-ai/glm-4.5-air"
```

The API key is valid; `z-ai/glm-4.5-air:free` no longer exists. All four model env vars hold that same dead slug, so fallback does nothing.

**Impact:** chatbot answers degrade to "I could not reach the language model right now" (retrieval still works and raw context is returned); diagnosis reports never leave `processing`; intent classification falls back to rule-based.

**Fix:** point the four variables at a currently-available model.

### 3. District Intelligence always fails ✗ HIGH

`KeyError: 'state'` on every request, swallowed at `district_intelligence.py:755`. Root cause: missing datasets (§7). All 7 insights return null. The 768-line engine — the project's most distinctive feature — never produces output.

### 4. `pest_level` at chance, poisoning the cascade ✗ HIGH

0.3335 val accuracy on 3 classes, self-flagged `"OVERFIT"`, and fed as a feature into dosage / timing / yield (§4.2).

### 5. Leakage-perfect scores ✗ HIGH

Crop recommender and fertilizer recommender at 1.0 on every split (§6). Confirmed in live inference: `rice 1.0, wheat 0.0, tobacco 0.0`.

### 6. `evaluation_graphs/` is entirely synthetic ✗ HIGH

`generate_evaluation_graphs.py` and `generate_llm_comparison_graphs.py` import **only** numpy, matplotlib, seaborn. Zero file I/O — no `joblib.load`, no `read_csv`, no `torch.load`. Every value is hardcoded or `np.random`:

```python
rf_vals  = [0.921, 0.981, 0.918, 0.914, 0.915]         # line 75
actual   = np.random.uniform(0.5, 8.0, 300)            # line 231
predicted= actual * np.random.normal(1.0, 0.08, 300)   # line 232
cm[i, i] = np.random.randint(90, 100)                  # line 116
```

All 29 PNGs — confusion matrices, residual plots, CNN training curves, federated convergence, LLM comparison radars — are plotted from invented numbers and watermarked "TerraMind © 2025 | Bennett University". The hardcoded values track the README's claims, not the trained models' actual metrics.

**These charts must not be presented as measured results.** Regenerating them from the real artifacts and test splits is the highest-leverage fix in the project.

### 7. `meta_learner/` dead ⚠ MED

Ensemble engine never executes (§5.5).

### 8. Federated unreachable from UI ⚠ MED

Works over the API; no UI path; incompatible response shape; 3 of 5 heads discarded; `paddy`/`rice` duplicate class (§5.4).

### 9. Duplicated stacks ⚠ MED

Two pre-sowing implementations, four duplicated modules (§3).

### 10. Repo weight ⚠ MED

`.git` 896 MB; a 332 MB pickle rewritten on every retrain (§7).

### 11. Process-local session state ⚠ MED

Chatbot gate is an in-process `set()` — resets on restart, breaks with `--workers > 1` (§4.3).

### 12. CORS misconfiguration ⚠ MED

`allow_origins=["*"]` with `allow_credentials=True` (`main.py:49-55`). Browsers reject that combination outright; credentialed cross-origin requests will fail.

### 13. No authentication ⚠ MED

`/train/all` and `/benchmark/all` are unauthenticated; only rate-limited.

### 14. No test suite ⚠ LOW

Four files, none a real suite: `test_integration.py`, `test_pred.py`, `backend/test_orchestrator.py` (scratch scripts), `graph_rag/retrieval/test_harness.py`.

### 15. Broad exception swallowing ⚠ LOW

`except Exception` counts: `run_simulation.py` 6, `data_partitioner.py` 6, `pre_sowing_pipeline.py` 5, `meta_learner/inference.py` 5, `query_engine.py` 5, `graph_rag_pipeline.py` 5, `external_sources.py` 5, `federated/inference.py` 5, `advisor.py` 5. This is what hides Issue #3.

### 16. `error.log` is dual-purpose ⚠ LOW

`orchestrator.py:71` appends structured routing JSON to the same file that receives stack traces. UTF-16 encoded, committed to git.

---

## 13. Discrepancies vs. `wholeprojectreadme.md`

| Claim | Reality | Source |
|---|---|---|
| Crop recommender ~92%, 22 classes | 1.0 on all splits, **10 classes** | `crop_recommendation/saved_models/metadata.json` |
| Yield: **XGBoost**, R² 0.87, MAE 0.31 | **RandomForest**, R² 0.8235, MAE 0.3749 | `yield_prediction/saved_models/metadata.json` |
| Pest level ~89% | **0.3335** | `evaluation_summary.json` |
| Fertilizer ~91% | 1.0 | `evaluation_summary.json` |
| FL: 20 rounds, 22 crops, 4 irrigation types | **5 rounds**, 11 crops, 3 types | `federated_model_metadata.json` |
| FL "within 3% gap" | FL *ahead* by 0.336 pp | `comparison.json` |
| CNN ~96% | No stored metric; 88 classes | `class_metadata_fast.json` |
| Irrigation need = mm/day **regression** | **Classifier** (low/med/high) | `irrigation_sunlight/saved_models/metadata.json` |
| Ensemble engine resolves conflicts | Dead code, never runs | grep: no importers |
| "Redundant crop labels merged" | `paddy` and `rice` both present in FL encoder | `federated_model_metadata.json` |
| Deployment via Render (`render.yaml`) | No `render.yaml`; Docker → HF Spaces | filesystem |
| Chatbot lives in `chatbot/` | `chatbot/` has only a README | filesystem |
| KG: 10+ crops, 12 pests, 8 diseases, 12 pesticides | 55 nodes / 117 edges total | `agrokg.pkl` |

`wholeprojectreadme.md` is best read as a design document describing intent. This file describes the code.

---

## 14. Appendix: Verified Run Output

Captured 2026-07-30, backend on `127.0.0.1:8011`, Python 3.14.4, sklearn 1.8.0, numpy 2.4.4, torch 2.11.0+cpu.

**Advisor** — `{N:90, P:42, K:43, ph:6.5, temp:21, humidity:82, rainfall:203, Punjab/Ludhiana, kharif, alluvial}`:

```json
{"crop_recommender": {"top_3": [{"crop":"rice","confidence":1.0},
                                {"crop":"wheat","confidence":0.0},
                                {"crop":"tobacco","confidence":0.0}],
                      "selected_crop":"rice","selected_confidence":1.0},
 "yield_predictor":  {"expected_yield":4.3092,"unit":"t/ha",
                      "confidence_band":{"lower":3.3959,"upper":5.2225}},
 "agri_condition_advisor": {"sunlight_hours":3.5,"irrigation_type":"rainfed",
                            "irrigation_need":"medium","district_prior_used":false},
 "district_intelligence": {"yield_trend":"unavailable","insights":[], ...}}
```

Note the 1.0/0.0/0.0 confidence split (Issue #5), `sunlight_hours` pinned to its 3.0 floor, `rainfed` for tube-well Punjab (Issue #4 class of problem), and null district intelligence (Issue #3).

**Monitor:**
```json
{"recommended_fertilizer":"Urea","pest_level":"High","dosage":95.4,
 "apply_after_days":15,"expected_yield_after_dosage":67.7}
```

**Diagnosis** on `sample_leaf.jpg`:
```json
{"identified_crop":"Rice","identified_class":"Rice__hispa","confidence":0.9132,
 "top_k_predictions":[{"crop":"Rice","class":"Rice__hispa","confidence":0.9132},
                      {"crop":"Rice","class":"Rice__leaf_blast","confidence":0.0247},
                      {"crop":"Tea","class":"Tea__healthy","confidence":0.0057}],
 "assistant_available":true,"report_id":"..."}
```

**Graph RAG health:** `{"status":"ok","provider":"openrouter","model":"z-ai/glm-4.5-air:free","kg_nodes":55}`

**FAISS index:** `ensure_loaded()` → 0.6 s, `is_loaded: True`, **8,327 chunks**

**Federated** — same soil inputs:
```json
{"success":true,"model_type":"federated","predicted_crop":"rice","confidence":0.9713,
 "yield_estimate_tons_per_hectare":4.89,
 "top_3_predictions":[{"crop":"rice","confidence":0.9713},
                      {"crop":"paddy","confidence":0.0213},
                      {"crop":"sugarcane","confidence":0.0019}],
 "federated_model_accuracy":0.970349,"centralized_model_accuracy":0.9671,
 "accuracy_gap_pct":-0.336}
```

`rice` and `paddy` as separate classes, visible in production output (§5.4).

**Gated flow:** diagnosis → `report_id` → `POST .../download` → `{"status":"ok"}` → `chatbot/ask` accepted, retrieval returned real KG + PDF context, LLM generation failed with the Issue #2 404.

**Route probes:** `/docs` `/metadata` `/sync/status` `/api/v1/*` → 200. `/health` `/api/states` `/api/districts/Punjab` → **404**.

---

*Generated from source inspection and live execution. Where this document and `wholeprojectreadme.md` disagree, this one describes what the code does.*
