# Trendscout Backend

FastAPI + SQLModel + PostgreSQL/pgvector. Python pipeline:
ingest → embed → topic model → time series → describe → persist.

## Layout

```
app/
  config.py            # pydantic-settings (.env)
  db.py                # engine, init_db (enables pgvector), session
  models.py            # SQLModel entities
  schemas.py           # API read/write models
  main.py              # FastAPI app
  cli.py               # `trendscout` CLI (init-db | run | research | serve)
  api/routes.py        # /health /runs /trends /trends/{id} /trends/{id}/feedback ...
  ingestion/           # source connectors (OpenAlex, arXiv, Firecrawl; geo, registry)
  pipeline/            # embeddings, topics, timeseries, describe, classify, run
  research/            # deep-research crawler: expansion, relevance gate, feedback, service
tests/                 # pytest (DB-backed tests skip if Postgres is unreachable)
```

## Pluggable components

| Stage | Offline fallback | Scientific (extra) |
|-------|------------------|--------------------|
| Embedder | `hashing` | `sentence_transformers` (ml), `openai` (llm) |
| Topic model | `simple` (KMeans + c-TF-IDF) | `bertopic` (ml) |
| Describer | `template` | `openai` (llm) |

Select via `.env` (`EMBEDDER`, `TOPIC_MODEL`, `DESCRIBER`, `EMBEDDING_DIM`).

## Commands

```bash
uv run trendscout init-db
uv run trendscout seed-demo              # load data/demo.sql into local Postgres
uv run trendscout run "circular construction facade" --limit 40
uv run trendscout research                 # bounded deep-research crawl (all sources)
uv run trendscout serve --reload
uv run pytest -q
uv run ruff check .
```
