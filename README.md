---
title: TerraMind
emoji: "🌱"
colorFrom: green
colorTo: blue
sdk: docker
pinned: false
---

# TerraMind: Smarter Farming, Every Stage
## Hybrid Edge-Enabled Pre-Sowing Advisor

A production-grade end-to-end agriculture intelligence platform for the **pre-sowing stage** featuring centralized ML models, edge-deployable compressed inference, bounded district-level adaptation, and a comprehensive benchmarking framework.

---

## Architecture

```
USER INPUT (N, P, K, pH, temp, humidity, rainfall, soil, state, district, season)
│
├─→ Model 1: Crop Recommender (RF/GB Classifier)
│     └─→ [Edge mode] Bounded Local Adaptation Layer
│           └─→ Top-3 crops + confidence
│
├─→ Model 2: Yield Predictor (GB Regressor + historical features)
│     └─→ Expected yield + confidence band
│
├─→ Model 3: Agri-Condition Advisor (3 sub-models)
│     ├─→ Sunlight hours (regression)
│     ├─→ Irrigation type (classification) ←─ District infra prior
│     └─→ Irrigation need (classification)
│
└─→ Novelty Layer: District Intelligence Engine
      ├─→ Crop area share
      ├─→ Yield trend analysis
      ├─→ Competing crops
      ├─→ Best historical season
      ├─→ 10-year trajectory
      └─→ Irrigation infrastructure summary
```

### Deployment Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **Central** | Full-power global model, no compression | Gold standard reference |
| **Edge** | Compressed model + local adaptation + cached priors | Low-latency offline-first production |
| **Local-Only** | Per-state partition trained models | Benchmarking only |

---

## Why This Is Edge-Enabled (Not Buzzword-Only)

1. **Central model** is trained on full data → serves as the gold standard
2. **Edge model** is a compressed version with reduced trees → smaller artifact, faster startup
3. **Local adaptation** applies bounded post-prediction adjustments using district priors — NOT full retraining
4. **All edge caches** (crop frequencies, irrigation infra, yield trajectories) are stored locally as JSON files
5. **No central server hit** needed for standard edge inference
6. **Sync workflow** supports pulling updated central artifacts when connectivity is available
7. **Federated updates** are architecturally supported but not forced

---

## Datasets

All datasets must be placed in `./dataset before sowing/`:

| File | Purpose |
|------|---------|
| `crop_dataset_rebuilt.csv` | Model 1: Crop Recommender |
| `irrigation_prediction.csv` | Model 3: Agri-Condition Advisor |
| `India Agriculture Crop Production.csv` | Model 2 + Intelligence |
| `crop_production.csv.xlsx` | Model 2 (secondary yield source) |
| `ICRISAT-District Level Data.csv` | District Intelligence |
| `ICRISAT-District Level Data Source.csv` | Irrigation Infrastructure |
| `ICRISAT-District Level Data Irrigation.csv` | Crop Irrigated Area |
| `main merge...xls` | Optional supplementary (graceful skip) |

---

## Installation

### Backend
```bash
cd backend
pip install -r requirements.txt
```

### Frontend
```bash
cd frontend
npm install
```

---

## Usage

### 1. Train All Models
```bash
# From project root
python -m backend.models.train_crop_recommender
python -m backend.models.train_yield_predictor
python -m backend.models.train_agri_advisor

# Or use the script:
scripts/train_all.bat       # Windows
bash scripts/train_all.sh   # Linux/Mac
```

### 2. Build Edge Assets
```bash
python -m backend.models.compress_edge_model

# Or:
scripts/build_edge_assets.bat
```

### 3. Run Backend
```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# Or:
scripts/run_backend.bat
```

### 4. Run Frontend
```bash
cd frontend
npm run dev

# Or:
scripts/run_frontend.bat
```

### 5. Run Benchmark
```bash
python -m backend.models.train_local_only_model
python -m backend.services.benchmark_service

# Or:
scripts/benchmark_all.bat
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/predict` | Full prediction pipeline |
| `POST` | `/train/all` | Train all models (background) |
| `POST` | `/benchmark/edge-assets` | Build edge artifacts |
| `POST` | `/benchmark/all` | Run benchmark comparison |
| `GET` | `/benchmark/results` | View benchmark results |
| `GET` | `/health` | Health check |
| `GET` | `/metadata` | Model versions & metrics |
| `GET` | `/sync/status` | Edge sync status |
| `POST` | `/sync/pull` | Pull central → edge |
| `GET` | `/api/states` | List states |
| `GET` | `/api/districts/{state}` | List districts |

### Sample Request
```json
{
  "N": 90, "P": 42, "K": 43, "ph": 6.5,
  "temperature": 25.0, "humidity": 80.0, "rainfall": 200.0,
  "soil_type": "loamy", "state": "Punjab", "district": "ludhiana",
  "season": "kharif", "area": 2.5, "mode": "edge"
}
```

---

## How Local Adaptation Works

1. Global crop recommender runs first → produces base probabilities
2. District-level priors are loaded from cached JSON files:
   - Crop frequency in district (area share)
   - Season suitability match
   - Yield history depth
3. Bounded probability adjustments are applied (max ±15% per crop)
4. Probabilities are re-normalised and crops re-ranked
5. All adjustments are logged and returned in the response

---

## Benchmark Target

| Metric | Target |
|--------|--------|
| Edge vs Central accuracy gap | ≤ 5 percentage points |
| Edge latency | < Central latency |
| Edge artifact size | < Central artifact size |

---

## Project Structure

```
├── backend/
│   ├── api/            # FastAPI route handlers
│   ├── app/            # FastAPI application entry
│   ├── artifacts/      # Trained model storage
│   │   ├── central/    # Full baseline models
│   │   ├── edge/       # Compressed + cached priors
│   │   └── local/      # Per-state benchmark models
│   ├── core/           # Config, logging
│   ├── models/         # Training scripts
│   ├── schemas/        # Pydantic schemas
│   ├── services/       # Business logic
│   └── utils/          # Data loading, preprocessing
├── frontend/           # React + Vite + Tailwind
├── scripts/            # Automation scripts
├── dataset before sowing/  # Input datasets
└── README.md
```

---

## Future Roadmap

- [ ] Federated learning aggregation (architecture hooks ready)
- [ ] Geospatial GEE enrichment (satellite imagery features)
- [ ] CNN disease detection module (during-growth stage)
- [ ] Market price prediction layer
- [ ] Fertilizer recommendation engine
- [ ] Multilingual support (Hindi, regional languages)
- [ ] ONNX export for mobile inference
- [ ] Real-time weather API integration

---

## Deploy On Render

This repository includes a Render Blueprint config at [render.yaml](render.yaml).

### 1. Push latest code to GitHub
- Ensure your latest branch includes `render.yaml`.

### 2. Create Blueprint in Render
- In Render dashboard: `New` -> `Blueprint`.
- Connect your GitHub repo and select this project.
- Render will detect `render.yaml` and create:
  - `terramind-backend` (FastAPI web service)
  - `terramind-frontend` (static site)

### 3. Set required secret
- In backend service env vars, set:
  - `OPENROUTER_API_KEY` = your OpenRouter key

### 4. Update frontend API URL (if service name differs)
- `render.yaml` frontend build uses:
  - `VITE_API_BASE_URL=https://terramind-backend.onrender.com`
- If your backend URL is different, update this value in `render.yaml` and redeploy.

### 5. Verify deployment
- Backend health: `https://<your-backend>.onrender.com/health`
- Graph RAG health: `https://<your-backend>.onrender.com/api/v1/graph-rag/health`
- Frontend should load and call backend routes under `/api/v1/*`.

### Notes
- Render free services may sleep when idle; first request can be slow.
- If your chatbot index relies on local PDFs, ensure those files are in repo (or mount persistent storage and rebuild index).
