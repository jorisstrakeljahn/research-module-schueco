# Trendscout Backend

FastAPI + SQLModel + PostgreSQL/pgvector. Python pipeline:
ingest → embed → topic model → time series → describe → persist.

## Prerequisites

- Docker (see root `README.md` — Postgres + pgvector run in a container)
- [uv](https://docs.astral.sh/uv/) — install once: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Root repo cloned; run backend commands from this directory

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
| Classifier | `heuristic` | `openai` (llm) |
| Translator | `none` (identity) | `openai` (llm) |

Select via `.env` (`EMBEDDER`, `TOPIC_MODEL`, `DESCRIBER`, `CLASSIFIER`, `TRANSLATOR`,
`EMBEDDING_DIM`). Every stage degrades to its offline fallback at runtime when the
extra is not installed, the API key is missing or the provider call fails — a run
never aborts because of an unavailable component. `TOPIC_MAX` (default 8) is a hard
cap on the number of clusters BERTopic may produce per run.

## Commands

```bash
uv sync --extra ml --extra llm           # install incl. Sentence-BERT/BERTopic/OpenAI
uv run trendscout init-db
uv run trendscout seed-demo              # load data/demo.sql into local Postgres
uv run trendscout run "circular construction facade" --limit 40
uv run trendscout research                 # bounded deep-research crawl (all sources)
uv run trendscout serve --reload
uv run pytest -q
uv run ruff check .
```
