# Trendscout – AI-assisted Trend Scouting Platform (Schüco)

Research module (M.Sc. Business Innovation & Technology, HSBI) · practice partner: Schüco International KG.

The platform ingests domain documents, structures them into topics, builds a
retrospective time series, describes each topic as a **trend**, and lets a human
expert review the result (human-in-the-loop). See `docs/` for the full plan and the
scientific justification of every decision.

## Architecture (v0)

```
OpenAlex ─▶ Ingestion ─▶ Embeddings ─▶ Topic modeling ─▶ Time series ─▶ Trend description
                                                                              │
                          PostgreSQL + pgvector  ◀───────────────────────────┘
                                   │
                         FastAPI  ─▶  Next.js frontend (Trendradar + expert review)
```

Each pipeline stage is pluggable with an **offline fallback** (runs with no API key)
and a **scientific/production** implementation (Sentence-BERT, BERTopic, LLM).

## Prerequisites

- Docker (for PostgreSQL + pgvector)
- [uv](https://docs.astral.sh/uv/) (Python 3.11–3.13)
- Node.js 20+

## Quickstart

```bash
# 1. Database
docker compose up -d db

# 2. Backend (offline defaults: no API key needed)
cd backend
uv venv && uv pip install -e .
uv run trendscout run "building facade adaptive" --limit 40   # one pipeline run
uv run trendscout serve                                       # API on :8000

# 3. Frontend (in a second terminal)
cd frontend
npm install
npm run dev                                                   # UI on :3000
```

Open http://localhost:3000.

## Tests

```bash
cd backend
docker compose up -d db      # DB-backed tests need this (otherwise auto-skipped)
uv run pytest                # 19 tests
uv run ruff check .
```

## Configuration

Copy `backend/.env.example` to `backend/.env`. Secrets (LLM / Firecrawl keys) go in
`.env` only and are never committed. To switch from the offline fallbacks to the
scientific components:

```bash
uv pip install -e ".[ml,llm]"   # sentence-transformers, bertopic, openai
# then in .env:  EMBEDDER=sentence_transformers  TOPIC_MODEL=bertopic  DESCRIBER=openai
```

## Documentation

- `docs/PROJEKTPLAN.md` – architecture, scope (MVP vs. later), data model, evaluation.
- `docs/ENTSCHEIDUNGEN-BELEGE.md` – decision records (ADR-01…ADR-21) with citations.
- `docs/LITERATUR-ORIENTIERUNG.md` – guiding literature (Fraunhofer 2025).
