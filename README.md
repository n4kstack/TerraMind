# TerraMind — Smarter Farming, Every Stage

An end-to-end agriculture intelligence platform that advises Indian farmers across the **entire crop lifecycle** — what to plant, how to manage it while it grows, what went wrong when leaves start spotting, and what the research literature says about it.

Four ML-backed modules sit behind one FastAPI service and one React SPA, served together from a single container.

**[▶ Live Demo — try TerraMind now](https://n4ksworks-terramind.hf.space/)**

> The Space runs on CPU Basic and sleeps when idle. The first request after a cold start can take 30–60 seconds while the model artifacts load.

---

## Table of Contents

- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
- [Usage Examples](#usage-examples)
- [API Endpoints](#api-endpoints)
- [Project Structure](#project-structure)
- [Retraining the Models](#retraining-the-models)
- [Deployment](#deployment)
- [Known Issues & Limitations](#known-issues--limitations)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Author](#author)
- [Acknowledgements](#acknowledgements)

---

## Key Features

### 🌱 Pre-Sowing Advisor
Recommends what to plant before the season starts, from soil and climate inputs.

- **Crop Recommender** — Random Forest / Gradient Boosting classifier returning top-3 crops with confidence
- **Yield Predictor** — Gradient Boosting regressor with historical district features and a confidence band
- **Agri-Condition Advisor** — three sub-models for sunlight hours, irrigation type, and irrigation need
- **District Intelligence Engine** — crop area share, yield trend, competing crops, best historical season, 10-year trajectory, and irrigation infrastructure, all read from cached district priors

### 🌿 Growth Stage Monitor
Advises mid-season, once the crop is in the ground: pest pressure level, recommended fertilizer, dosage, application window, and expected yield after treatment.

### 🔬 Post-Symptom Diagnosis
Upload a leaf photo and get a disease classification across 88 crop/disease classes, with a downloadable PDF report. The CNN ships with the repo — clone with Git LFS, or the weights arrive as a pointer file and the endpoint returns 503.

### 📚 AugNosis — Graph RAG + Document Assistant
Grounded question answering over agricultural literature, combining:

- A **NetworkX knowledge graph** of crops, diseases, and treatments
- **FAISS** semantic retrieval over indexed PDFs
- Live adapters for **AGRIS (FAO)**, **AGRICOLA (USDA NAL)**, CABI, PubAg, OpenAlex, EuropePMC, FAOSTAT, CGIAR, AgEcon, and ASABE
- Retrieval guardrails and a refusal path when sources don't support an answer

### ⚡ Hybrid Edge Architecture
Three deployment modes from one codebase:

| Mode | What it does | Use case |
|------|--------------|----------|
| **Central** | Full-power global models, no compression | Gold-standard reference |
| **Edge** | Compressed models + bounded local adaptation + cached JSON priors | Low-latency, offline-first |
| **Local-Only** | Per-state partition models | Benchmarking only |

Edge inference needs no central server. Local adaptation applies **bounded** post-prediction adjustments (max ±15% per crop) from district priors — not a full retrain — and every adjustment is logged into the response.

---

## Tech Stack

**Backend**
| Tool | Role |
|------|------|
| FastAPI + Uvicorn | API framework and ASGI server |
| Pydantic v2 | Request/response schemas and validation |
| SlowAPI | Per-endpoint rate limiting |
| scikit-learn `1.8.0` | Classical ML models (**pin is mandatory** — see Known Issues) |
| NumPy 2.x / SciPy / pandas | Numerics and data handling |
| joblib | Model serialization |

**ML & AI**
| Tool | Role |
|------|------|
| PyTorch + torchvision | Disease-detection CNN, federated simulation |
| sentence-transformers | `all-MiniLM-L6-v2` embeddings |
| FAISS (`faiss-cpu`) | Vector similarity search |
| NetworkX | Agricultural knowledge graph |
| PyMuPDF | PDF text extraction |
| OpenRouter | Hosted LLM inference for report generation |

**Frontend**
| Tool | Role |
|------|------|
| React 18 + TypeScript | UI |
| Vite 8 | Build tool and dev server |
| Tailwind CSS 3 | Styling |
| Radix UI | Accessible primitives (dialog, popover, tabs, tooltip) |
| Framer Motion | Animation |
| Recharts | Yield trajectory charts |
| React Router 7 | Routing |
| jsPDF + react-markdown | Report export and rendering |

**Infrastructure** — Docker (multi-stage: `node:20-alpine` → `python:3.11-slim`), Hugging Face Spaces, Git LFS for model binaries.

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| **Python** | 3.11 | The Docker image pins `python:3.11-slim` |
| **Node.js** | 20+ | For the frontend build |
| **Git LFS** | any | **Required.** See the warning below |
| **RAM** | 4 GB+ | Model artifacts total ~390 MB on disk |
| **Disk** | ~1.5 GB | Repo + dependencies |

> ### ⚠️ Git LFS is not optional
>
> Every model file (`.pkl`, `.joblib`, `.pth`, `.bin`, images) is stored in Git LFS. Cloning **without** LFS installed gives you ~180 small text pointer files instead of real models, and the app fails at startup with deserialization errors.
>
> ```bash
> git lfs install     # run once per machine, BEFORE cloning
> ```
>
> Already cloned without it? Recover with `git lfs install && git lfs pull`.

---

## Installation

```bash
# 1. Install Git LFS first (see warning above)
git lfs install

# 2. Clone
git clone https://github.com/n4kstack/TerraMind.git
cd TerraMind

# 3. Verify LFS actually pulled the models — this must print ~5.5M, not ~130 bytes
ls -lh backend/artifacts/central/yield_predictor/model.joblib

# 4. Backend dependencies
pip install -r backend/requirements.txt

# 5. Frontend dependencies
cd frontend && npm install && cd ..
```

**No training is required to run the project.** All model artifacts are committed, so the app works immediately after install.

---

## Configuration

Copy the template and edit as needed:

```bash
cp .env.example .env                    # backend
cp frontend/.env.example frontend/.env  # frontend
```

Every variable has a working default — **the only one you may need to set is the LLM key**, and only for the AugNosis / chatbot modules. The advisor, monitor, and diagnosis modules run fully offline.

### Core variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENROUTER_API_KEY` | *(none)* | **Secret.** Required for AugNosis and the chatbot |
| `OPENROUTER_MODEL_NAME` | `nvidia/nemotron-3-ultra-550b-a55b:free` | Primary LLM |
| `GRAPH_RAG_FALLBACK_MODEL` | `nvidia/nemotron-3-super-120b-a12b:free` | Used when the primary is rate-limited |
| `GRAPH_RAG_MODEL_CANDIDATES` | `google/gemma-4-31b-it:free` | Ordered fallback list (comma-separated) |
| `GRAPH_RAG_LLM_MAX_TOKENS` | `4000` | Must cover reasoning **plus** the full JSON report, or output truncates |
| `TERRAMIND_HOST` / `TERRAMIND_PORT` | `0.0.0.0` / `8000` | Bind address (Docker uses `7860`) |
| `TERRAMIND_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformer for embeddings |
| `TERRAMIND_TOP_K` | `5` | Retrieved chunks per query |
| `TERRAMIND_SIM_THRESHOLD` | `0.35` | Minimum similarity to accept a chunk |
| `VITE_API_BASE_URL` | *(empty)* | Frontend only. **Leave empty in production** — empty means same-origin |

Rate limits (`TERRAMIND_*_RATE_LIMIT`), chunking, and diagnosis tunables are all listed in [.env.example](.env.example).

> **Never commit a real `.env`.** [.gitignore](.gitignore) and [.dockerignore](.dockerignore) both exclude it. Setting `VITE_API_BASE_URL` in production is a common mistake — it bakes an absolute URL into the bundle, so browsers call *that* host instead of the server they loaded the page from.

---

## Running the Project

### Option A — Docker (matches production exactly)

```bash
docker build -t terramind .
docker run -p 7860:7860 --env-file .env terramind
```

Open **http://localhost:7860** — the container serves both the API and the UI.

### Option B — Local development (hot reload)

Two terminals:

```bash
# Terminal 1 — backend on :8000
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
# Terminal 2 — frontend on :3000
cd frontend && npm run dev
```

Open **http://localhost:3000**. Set `VITE_API_BASE_URL=http://localhost:8000` in `frontend/.env` so the SPA finds the API across ports.

Windows helper scripts: `scripts/run_backend.bat`, `scripts/run_frontend.bat`.

### Verify it's up

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/graph-rag/health
```

Interactive API docs: **http://localhost:8000/docs**

---

## Usage Examples

### Pre-sowing crop recommendation

```bash
curl -X POST http://localhost:8000/api/v1/advisor/predict \
  -H "Content-Type: application/json" \
  -d '{
    "N": 90, "P": 42, "K": 43, "ph": 6.5,
    "temperature": 25.0, "humidity": 80.0, "rainfall": 200.0,
    "soil_type": "loamy", "state": "Punjab", "district": "ludhiana",
    "season": "kharif", "area": 2.5, "model_mode": "standard"
  }'
```

Returns top-3 crops with confidence, predicted yield with a band, irrigation and sunlight guidance, and the district intelligence block.

`model_mode` accepts `standard` or `federated`. `state`/`district` are accepted as aliases for `state_name`/`district_name`, and `area` is optional.

> Don't confuse this with the legacy `POST /predict` route, which takes a different `mode` field (`central` / `edge` / `local_only`). The v1 endpoint ignores unknown keys silently, so a misplaced `mode` fails quietly rather than erroring.

### Growth-stage advisory

```bash
curl -X POST http://localhost:8000/api/v1/monitor/predict \
  -H "Content-Type: application/json" \
  -d '{
    "temperature": 30, "humidity": 65, "moisture": 40,
    "soil_type": "Loamy", "crop_type": "Wheat",
    "N": 80, "P": 40, "K": 40, "ph": 6.8, "rainfall": 120
  }'
```

### Disease diagnosis from a leaf photo

```bash
curl -X POST "http://localhost:8000/api/v1/diagnosis/predict?top_k=3" \
  -F "file=@leaf.jpg"
```

### Grounded literature query

```bash
curl -X POST http://localhost:8000/api/v1/graph-rag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How do I manage rice blast in Punjab?", "use_llm": true}'
```

### Frontend routes

| Route | Page |
|-------|------|
| `/` | Landing |
| `/advisor` | Pre-Sowing Advisor |
| `/monitor` | Growth Stage Monitor |
| `/diagnosis` | Post-Symptom Diagnosis |
| `/augnosis` | Graph RAG + document assistant |

---

## API Endpoints

Interactive docs at `/docs` (Swagger) and `/redoc`.

### Unified v1 API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/advisor/predict` | Full pre-sowing pipeline |
| `POST` | `/api/v1/advisor/compare` | Compare central vs edge vs local output |
| `POST` | `/api/v1/advisor/train/all` | Retrain all pre-sowing models |
| `GET` | `/api/v1/advisor/metadata` | Model versions and metrics |
| `POST` | `/api/v1/monitor/predict` | Growth-stage advisory |
| `POST` | `/api/v1/diagnosis/predict` | Leaf image → disease |
| `GET` | `/api/v1/diagnosis/report/{report_id}` | Fetch a generated report |
| `POST` | `/api/v1/diagnosis/report/{report_id}/download` | Download report as PDF |
| `POST` | `/api/v1/chatbot/ask` | Ask the document assistant |
| `GET` | `/api/v1/chatbot/status` | Index status |
| `POST` | `/api/v1/chatbot/rebuild` | Rebuild the FAISS index |
| `POST` | `/api/v1/graph-rag/query` | Grounded knowledge-graph query |
| `GET` | `/api/v1/graph-rag/health` | LLM + knowledge-graph health |

### Platform & edge-management routes

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service health check |
| `GET` | `/api/states` | List all states |
| `GET` | `/api/districts/{state}` | List districts for a state |
| `POST` | `/predict` | Edge/central prediction (legacy surface) |
| `GET` | `/metadata` | Artifact versions |
| `GET` | `/sync/status` | Edge sync status |
| `POST` | `/sync/pull` | Pull central artifacts → edge |
| `POST` | `/train/all` | Retrain everything (background) |
| `POST` | `/train/{crop-recommender\|yield-predictor\|agri-advisor}` | Retrain one model |
| `POST` | `/benchmark/all` | Run the benchmark suite |
| `GET` | `/benchmark/results` | Read benchmark results |
| `POST` | `/benchmark/edge-assets` | Build edge artifacts and caches |

---

## Project Structure

```
TerraMind/
├── backend/
│   ├── api/                  # Platform routes: predict, train, sync, benchmark
│   ├── app/
│   │   ├── api/v1/           # Unified v1 API (advisor, monitor, diagnosis,
│   │   │                     #   chatbot, graph_rag)
│   │   ├── chatbot/          # RAG: ingestion, retrievers, router, storage
│   │   ├── core/             # Config, rate limiting, runtime config
│   │   ├── schemas/          # Pydantic models
│   │   ├── services/         # Business logic
│   │   └── main.py           # FastAPI entry point + SPA mounting
│   ├── artifacts/            # Trained models (Git LFS)
│   │   ├── central/          # Full-power baseline
│   │   ├── edge/             # Compressed models + district JSON priors
│   │   └── local/            # Per-state benchmark models
│   ├── core/                 # Paths, hyperparameters, logging
│   ├── models/               # Training + edge-compression scripts
│   ├── services/             # Inference pipeline, district intelligence, sync
│   └── utils/                # Feature engineering, caches, normalizers
├── ml/
│   ├── pre_sowing_advisor/   # Crop rec, yield, irrigation/sunlight
│   ├── growth_stage_monitor/ # Pest, fertilizer, dosage models
│   └── post_symptom_diagnosis/  # Disease CNN inference wrappers
├── graph_rag/
│   ├── retrieval/adapters/   # AGRIS, AGRICOLA, CABI, PubAg, OpenAlex, …
│   ├── graph_builder.py      # Knowledge graph construction
│   └── graph_rag_pipeline.py # Orchestration
├── federated/                # Flower-based 28-state FL simulation
├── meta_learner/             # RF + federated ensemble fusion
├── frontend/
│   ├── src/
│   │   ├── components/       # UI primitives, layout, theme
│   │   ├── features/         # advisor, diagnosis, landing
│   │   ├── pages/            # Route components
│   │   └── lib/api/          # Typed API client
│   └── vite.config.js
├── scripts/                  # Train / benchmark / run helpers (.sh + .bat)
├── Dockerfile                # Multi-stage: node build → python runtime
└── .env.example
```

---

## Retraining the Models

**Skip this unless you're changing the models** — trained artifacts ship with the repo.

Datasets are **not** included (they're gitignored due to size). To retrain, place the CSVs where the config expects them:

- `dataset before sowing/` — see [backend/core/config.py](backend/core/config.py#L14)
- `dataset during growth/` — see [ml/growth_stage_monitor/config.py](ml/growth_stage_monitor/config.py#L10)

| File | Feeds |
|------|-------|
| `crop_dataset_rebuilt.csv` | Crop Recommender |
| `irrigation_prediction.csv` | Agri-Condition Advisor |
| `India Agriculture Crop Production.csv` | Yield Predictor + District Intelligence |
| `ICRISAT-District Level Data*.csv` | District Intelligence + Irrigation Infrastructure |
| `fertilizer_giant_training_dataset.csv` | Growth Stage Monitor |

```bash
# Train
python -m backend.models.train_crop_recommender
python -m backend.models.train_yield_predictor
python -m backend.models.train_agri_advisor
#   or: scripts/train_all.sh  /  scripts/train_all.bat

# Build compressed edge artifacts + district caches
python -m backend.models.compress_edge_model
#   or: scripts/build_edge_assets.sh

# Benchmark central vs edge vs local
python -m backend.models.train_local_only_model
python -m backend.services.benchmark_service
#   or: scripts/benchmark_all.sh
```

**Benchmark targets:** edge-vs-central accuracy gap ≤ 5 pp, edge latency below central, edge artifact smaller than central.

---

## Deployment

Deployed as a **single Docker container** on Hugging Face Spaces — FastAPI serves the API and the built SPA from one origin on port `7860`.

1. Create a Space with SDK `Docker`, hardware `CPU Basic`
2. Connect this repository
3. Add `OPENROUTER_API_KEY` under **Secrets**
4. Copy the rest from [HUGGINGFACE_VARIABLES.env.example](HUGGINGFACE_VARIABLES.env.example) into **Variables**
5. Push — the Space builds from the [Dockerfile](Dockerfile) automatically

Full walkthrough: [README_HUGGINGFACE.md](README_HUGGINGFACE.md).

> **The Space needs a YAML frontmatter block that this README deliberately omits.** Hugging Face reads `sdk: docker` and the Space title from frontmatter at the top of `README.md`; GitHub renders that same block as a raw table, so it lives on the deploy branch only. Copy it from [README_HUGGINGFACE.md](README_HUGGINGFACE.md#-required-space-frontmatter-on-the-deploy-branch) before pushing to the Space.

> **`backend/artifacts/` must be present in the deployed image.** Without it the model registry raises `FileNotFoundError` and `/predict` silently degrades to a fallback that never sees state or district — every district then returns the identical crop and confidence.

---

## Known Issues & Limitations

- **Disease diagnosis weights are LFS-tracked, so a plain clone won't run it.** The CNN artifacts now ship with the repo at `ml/post_symptom_diagnosis/saved_models/trained_artifacts_fast/`, but a clone made without Git LFS leaves the 14 MB TorchScript export as a 133-byte pointer file, and `/api/v1/diagnosis/predict` answers `503 Diagnosis model is not available`. Run `git lfs pull` after cloning.

- **Dependency versions are load-bearing.** `scikit-learn==1.8.0` and `numpy>=2.0,<3` are pinned exactly because the committed models embed the library versions that serialized them. Installing a different scikit-learn breaks unpickling with `No module named '_loss'`, and every advisor request fails. Don't relax these pins without retraining.

- **~66 MB of duplicated artifacts.** 18 files under `backend/artifacts/central/` are byte-identical to their `edge/` counterparts, including a 47.5 MB model — `compress_edge_model.py` only genuinely compresses the crop recommender and copies the rest verbatim. Both trees are read at runtime, so neither can simply be deleted.

- **Unreachable code paths.** `backend/app/api/router.py` and `routers/graph_rag_router.py` are never mounted — `main.py` includes the v1 routers directly. Likewise `federated/` and `meta_learner/` are not imported by the API; they exist as a standalone simulation.

- **Free-tier LLM rate limits.** AugNosis depends on free OpenRouter models. Under load the primary model rate-limits and the pipeline falls back down `GRAPH_RAG_MODEL_CANDIDATES`; if all are exhausted, responses degrade to retrieval-only.

- **Large clone.** ~356 MB via Git LFS. Shallow-clone if you only need the source: `git clone --depth 1`.

- **Cold starts.** CPU Basic Spaces sleep when idle; the first request loads ~390 MB of artifacts.

- **No automated test suite.** There is no pytest suite or CI pipeline yet.

---

## Roadmap

- [ ] Automated test suite + CI
- [ ] Federated learning aggregation wired into the live API
- [ ] Geospatial GEE enrichment (satellite imagery features)
- [ ] Market price prediction layer
- [ ] Multilingual support (Hindi and regional languages)
- [ ] ONNX export for on-device mobile inference
- [ ] Real-time weather API integration
- [ ] Deduplicate the central/edge artifact overlap

---

## Contributing

Contributions are welcome.

1. Fork the repo and create a branch — `git checkout -b feature/your-feature`
2. **Run `git lfs install` before cloning**, or model files will be pointers
3. Keep changes focused; match the surrounding code style
4. Never commit `.env` files, datasets, or regenerated artifacts — check `git status` against [.gitignore](.gitignore)
5. Write commit messages in the existing convention: `type(scope): summary` (e.g. `fix(yield): enrich district history before scaling`)
6. Explain *why* in the commit body, not just *what*
7. Open a pull request against `main`

If you're adding a new retrieval adapter, follow the interface in [graph_rag/retrieval/adapters/base.py](graph_rag/retrieval/adapters/base.py).

---

## License

**No license file is currently included in this repository.**

Under default copyright, that means all rights are reserved and others have no legal permission to use, modify, or redistribute this work — even though the source is publicly visible.

If you intend this to be open source, add a `LICENSE` file (MIT and Apache-2.0 are common choices for ML projects) and update this section.

---

## Author

**Nakul**

- GitHub — [@n4kstack](https://github.com/n4kstack)
- LinkedIn — [Nakul Sharma](https://www.linkedin.com/in/nakul-sharma-21699a286)
- Project — [github.com/n4kstack/TerraMind](https://github.com/n4kstack/TerraMind)

---

## Acknowledgements

**Data sources**
- [ICRISAT](http://data.icrisat.org/dld/) — district-level agricultural data for India
- India Agriculture Crop Production statistics — district-wise yield history
- [FAO AGRIS](https://agris.fao.org/) — Open Data Set catalogue and bibliographic records
- [USDA NAL AGRICOLA](https://agricola.nal.usda.gov/) and [PubAg](https://pubag.nal.usda.gov/)
- [CABI Digital Library](https://www.cabidigitallibrary.org/), [OpenAlex](https://openalex.org/), [Europe PMC](https://europepmc.org/), [FAOSTAT](https://www.fao.org/faostat/), [CGIAR](https://www.cgiar.org/), AgEcon Search, ASABE
- [HWSD](https://www.iiasa.ac.at/) — Harmonized World Soil Database

**Libraries & platforms**
- [FastAPI](https://fastapi.tiangolo.com/), [scikit-learn](https://scikit-learn.org/), [PyTorch](https://pytorch.org/), [FAISS](https://faiss.ai/), [sentence-transformers](https://sbert.net/), [NetworkX](https://networkx.org/)
- [React](https://react.dev/), [Vite](https://vite.dev/), [Tailwind CSS](https://tailwindcss.com/), [Radix UI](https://www.radix-ui.com/)
- [Hugging Face Spaces](https://huggingface.co/spaces) for hosting, [OpenRouter](https://openrouter.ai/) for LLM inference
