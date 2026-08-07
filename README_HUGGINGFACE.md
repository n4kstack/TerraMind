# TerraMind on Hugging Face Spaces (Docker)

This repo is prepared for a **single Hugging Face Space** deployment where:
- FastAPI backend runs on port `7860`
- Frontend is built inside Docker and served by FastAPI

## ⚠️ Required: Space frontmatter on the deploy branch

Hugging Face reads a Space's configuration from a YAML frontmatter block at the
very top of `README.md`. **Without it the Space does not know it is a Docker
Space** and the build fails or falls back to the wrong SDK.

That block is deliberately **not** in the GitHub `README.md`: GitHub renders
frontmatter as a raw key/value table above the title, which is noise for anyone
reading the project page.

So the deploy branch must carry it and `main` must not. Before pushing to the
Space, prepend this to `README.md` on the deploy branch:

```yaml
---
title: TerraMind
emoji: "🌱"
colorFrom: green
colorTo: blue
sdk: docker
pinned: false
---
```

Verify it survived the push — this must print the block, not the project title:

```bash
git show hf/main:README.md | head -8
```

## 1. Before Deploying

1. Push this repository to GitHub.
2. Rotate your OpenRouter API key if it has ever been committed/shared.

## 2. Create Space

1. Go to Hugging Face -> `New Space`
2. Choose:
   - Space SDK: `Docker`
   - Visibility: your choice
   - Hardware: `CPU Basic` (start here)
3. Connect to your GitHub repo (or upload files directly).

## 3. Set Space Secrets

In Space Settings -> Variables and secrets, add:

- You can copy from `HUGGINGFACE_VARIABLES.env.example` for Variables.

- `OPENROUTER_API_KEY` (secret)
- `OPENROUTER_MODEL_NAME` = `nvidia/nemotron-3-ultra-550b-a55b:free`
- `OPENROUTER_TEMPERATURE` = `0.3`
- `OPENROUTER_TIMEOUT` = `240`
- `OPENROUTER_REASONING_EFFORT` = `low`
- `GRAPH_RAG_MODEL` = `nvidia/nemotron-3-ultra-550b-a55b:free`
- `GRAPH_RAG_FALLBACK_MODEL` = `nvidia/nemotron-3-super-120b-a12b:free`
- `GRAPH_RAG_MODEL_CANDIDATES` = `google/gemma-4-31b-it:free`
- `GRAPH_RAG_LLM_MAX_TOKENS` = `4000`
- `GRAPH_RAG_LLM_RETRY_MAX_TOKENS` = `5000`
- `TERRAMIND_REPORT_NUM_PREDICT` = `5000`

Optional overrides:
- `TERRAMIND_TOP_K`
- `TERRAMIND_SIM_THRESHOLD`
- `TERRAMIND_MAX_CONTEXT_CHUNKS`

## 4. Deploy

- Commit and push.
- Hugging Face will build with `Dockerfile` automatically.
- Wait for status `Running`.

## 5. Verify

Open your Space URL and test:

- `/health`
- `/docs`
- `/api/v1/graph-rag/health`

## 6. If Build Fails

- Check Space `Build logs` for missing packages.
- If GraphRAG needs additional Python packages not in `backend/requirements.txt`, add them there and redeploy.
- Frontend build runs inside Docker automatically, so you do not need to commit `frontend/dist` for Spaces.

## 7. Local Docker Test (Optional)

```bash
docker build -t terramind-hf .
docker run -p 7860:7860 --env-file .env terramind-hf
```

Then open `http://localhost:7860`.
