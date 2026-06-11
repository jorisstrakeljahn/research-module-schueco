# AGENTS.md

## What this is

AI-assisted trend-scouting research module (M.Sc. Business Innovation & Technology,
HSBI × practice partner Schüco). Monorepo:

- `backend/` — FastAPI + SQLModel pipeline (ingest → embed → topics → describe →
  classify), PostgreSQL/pgvector, managed with **uv**.
- `frontend/` — Next.js 16 + Tailwind Trendradar UI.

## Verify your changes

| Area | Command (from repo root) |
|---|---|
| Backend lint | `cd backend && uv run ruff check .` |
| Backend tests | `cd backend && docker compose up -d db && uv run pytest` |
| Frontend lint | `cd frontend && npm run lint` |
| Frontend types | `cd frontend && npm run typecheck` |
| Frontend build | `cd frontend && npm run build` |

CI runs the same checks (`.github/workflows/ci.yml`); DB-backed tests fail loudly
in CI instead of skipping.

## Conventions

- uv **project mode** — use `uv sync` / `uv run`, never bare `pip` or `uv pip`.
- Config via pydantic-settings; copy `backend/.env.example` → `backend/.env`,
  `frontend/.env.example` → `frontend/.env.local`. Secrets live only in `.env*`.
- Every pipeline stage has an **offline fallback** plus an optional scientific
  implementation behind extras (`ml`, `llm`). Keep new components pluggable via the
  existing Protocol + factory pattern.
- Conventional commits.

## Gotchas

- Postgres runs on host port **5433** (not 5432) — see `docker-compose.yml`.
- DB-backed tests auto-skip without Docker locally, but fail loudly in CI.
- `EMBEDDING_DIM` must match the active embedder; `init_db` fails fast on a
  pgvector dimension mismatch.
- State-changing API routes require a bearer token when `API_TOKEN` is set.
- The frontend has its own `frontend/AGENTS.md` with a Next.js 16 warning — read it
  before touching frontend code.

## Where things are

- `docs/` — German project plan, ADRs, Schüco reference (maintainer-owned).
- `plans/` — numbered implementation plans + index.
- `backend/app/{api,ingestion,pipeline,research}` — the moving parts.
