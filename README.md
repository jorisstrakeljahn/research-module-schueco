# Trendscout

AI-assisted trend-scouting platform — research module (M.Sc. Business Innovation &
Technology, HSBI) with practice partner **Schüco International KG**.

It ingests domain documents (OpenAlex, arXiv, Firecrawl), clusters them into topics,
builds a retrospective time series, describes each topic as a **trend** (RAG + LLM),
assesses it (PESTEL · category · impact/urgency → Act/Prepare/Watch) and lets an expert
review the result. The frontend renders a Schüco-style **Trendradar**.

Every pipeline stage has an **offline fallback** (runs with no API key) and a
**scientific** implementation (Sentence-BERT, BERTopic, LLM).

```
sources ─▶ ingest ─▶ embed ─▶ topics ─▶ time series ─▶ describe ─▶ classify (PESTEL/impact)
                                  └── PostgreSQL + pgvector ──┘
                          FastAPI  ─▶  Next.js (Trendradar + expert review)
```

## Prerequisites

Install these **before** the Quickstart (each is a hard requirement):

| Tool | Purpose | Check |
|------|---------|-------|
| **Docker Desktop** | PostgreSQL + pgvector (in container) | `docker info` |
| **[uv](https://docs.astral.sh/uv/)** | Python deps + backend CLI | `uv --version` |
| **Node.js 20+** | Frontend | `node --version` |

### Install uv (one-time)

[uv](https://docs.astral.sh/uv/) is the Python package manager for the backend. It also
downloads a compatible Python automatically — no separate Python install needed.

**macOS / Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then restart the terminal (or run `source $HOME/.local/bin/env`).

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Alternative:** `brew install uv` (macOS) or `pip install uv`.

Verify: `uv --version` — then continue with Quickstart below.

### Install Docker Desktop (one-time)

Download [Docker Desktop](https://www.docker.com/products/docker-desktop/), install,
start it and wait until the engine is running. pgvector is **not** installed separately —
it ships inside the `pgvector/pgvector:pg16` image from `docker compose up -d db`.

If the pull fails with `500 Internal Server Error`, restart Docker Desktop and run
`docker pull pgvector/pgvector:pg16` before `docker compose up -d db`.

## Quickstart (demo UI)

Load the committed demo snapshot first — no API keys and no pipeline run needed:

```bash
# 1. Database
docker compose up -d db

# 2. Backend
cd backend
uv sync
cp .env.example .env
uv run alembic upgrade head
uv run trendscout seed-demo   # loads data/demo.sql (~50 trends)
uv run trendscout serve       # API on :8000

# 3. Frontend (second terminal)
cd frontend
npm install
npm run dev                   # UI on :3000
```

Open http://localhost:3000 — Dashboard, Portfolio and Trendradar show the persistent
trend portfolio. Run history, diffs and review decisions remain traceable separately.

To regenerate your own data instead, skip `seed-demo` and run the pipeline:

```bash
uv run trendscout run "building facade adaptive" --limit 40   # one simple run
uv run trendscout research                                    # bounded deep-research crawl
```

Maintainers can refresh the snapshot after a good pipeline run:

```bash
./scripts/export-demo.sh
cd backend
uv run python scripts/eval/parse_snapshot.py --run-id <id>
uv run python scripts/eval/topic_comparison.py --run-id <id>
```

The evaluator accepts only runs with an explicit `run_document` corpus snapshot.
Legacy Run 7 remains the immutable expert-evaluation baseline and is deliberately
not reinterpreted as a reproducible BERTopic run.

### Troubleshooting

**`expected 384 dimensions, not 1536` (or the reverse) during `seed-demo`**

The local Postgres volume was created with a different `EMBEDDING_DIM` than your
current `.env`. Reset the DB volume and import again (fresh clone path):

```bash
docker compose down -v
docker compose up -d db
cd backend && uv run trendscout seed-demo
```

Keep `EMBEDDING_DIM=384` from `.env.example` — the committed demo snapshot ships
without embedding vectors (UI data only).

**`uv: command not found`**

Install uv first (see [Install uv](#install-uv-one-time) above), restart the terminal,
then continue from `cd backend`.

## Tests

```bash
cd backend
docker compose up -d db      # DB-backed tests need this (otherwise auto-skipped)
uv run pytest
uv run ruff check .
```

## Configuration

Copy `backend/.env.example` to `backend/.env`; secrets (LLM / Firecrawl keys) live in
`.env` only. Sentence-Transformer embeddings and BERTopic are the application defaults;
tests explicitly select the deterministic offline fallbacks. Optional services are enabled
by adding their server-side credentials:

```bash
uv sync --extra ml --extra llm
# then in backend/.env:
#   FIRECRAWL_API_KEY=...
#   OPENAI_API_KEY=...
#   DESCRIBER=openai  CLASSIFIER=openai  EXPANDER=openai
```

## Layout

```
backend/   FastAPI app, ingestion connectors, analysis pipeline, CLI (uv)
frontend/  Next.js + Tailwind UI (Trendradar, dashboard, expert review)
data/      demo.sql snapshot loaded by `trendscout seed-demo`
scripts/   export-demo.sh to refresh the snapshot (maintainers)
```
