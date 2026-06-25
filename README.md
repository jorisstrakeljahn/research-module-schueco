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

- Docker (PostgreSQL + pgvector)
- [uv](https://docs.astral.sh/uv/) (Python 3.11–3.13)
- Node.js 20+

## Quickstart (demo UI)

Load the committed demo snapshot first — no API keys and no pipeline run needed:

```bash
# 1. Database
docker compose up -d db

# 2. Backend
cd backend
uv sync
cp .env.example .env
uv run trendscout seed-demo   # loads data/demo.sql (~50 trends)
uv run trendscout serve       # API on :8000

# 3. Frontend (second terminal)
cd frontend
npm install
npm run dev                   # UI on :3000
```

Open http://localhost:3000 — Dashboard, Newsfeed and Trendradar show the demo trends
from the latest completed run.

To regenerate your own data instead, skip `seed-demo` and run the pipeline:

```bash
uv run trendscout run "building facade adaptive" --limit 40   # one simple run
uv run trendscout research                                    # bounded deep-research crawl
```

Maintainers can refresh the snapshot after a good pipeline run:

```bash
./scripts/export-demo.sh
```

## Tests

```bash
cd backend
docker compose up -d db      # DB-backed tests need this (otherwise auto-skipped)
uv run pytest
uv run ruff check .
```

## Configuration

Copy `backend/.env.example` to `backend/.env`; secrets (LLM / Firecrawl keys) live in
`.env` only. Switch from the offline fallbacks to the scientific components:

```bash
uv sync --extra ml --extra llm
# then in .env:
#   EMBEDDER=sentence_transformers  TOPIC_MODEL=bertopic
#   DESCRIBER=openai  CLASSIFIER=openai
#   SOURCES=openalex,arxiv,firecrawl
```

## Layout

```
backend/   FastAPI app, ingestion connectors, analysis pipeline, CLI (uv)
frontend/  Next.js + Tailwind UI (Trendradar, dashboard, expert review)
data/      demo.sql snapshot loaded by `trendscout seed-demo`
scripts/   export-demo.sh to refresh the snapshot (maintainers)
```
