"""Command-line interface for the trendscout backend."""

from __future__ import annotations

import typer
from sqlmodel import Session

from app.config import get_settings
from app.db import get_engine, init_db

app = typer.Typer(help="Trendscout backend CLI")


@app.command("init-db")
def init_db_command() -> None:
    """Enable pgvector and create all tables."""
    init_db()
    typer.echo("Database initialized.")


@app.command("run")
def run_command(
    query: str = typer.Argument(..., help="Search query for the domain, e.g. 'facade'"),
    limit: int = typer.Option(50, help="Max documents to fetch"),
    language: str = typer.Option(None, help="Output language: en | de (overrides .env)"),
) -> None:
    """Run one full pipeline (ingest -> embed -> topics -> describe -> persist).

    Fetches ``query`` once from every enabled source (SOURCES) - the simple,
    non-iterative counterpart to ``research``.
    """
    from app.research.service import run_simple_search

    init_db()
    with Session(get_engine()) as session:
        run = run_simple_search(query, session=session, limit=limit, language=language)
    typer.echo(
        f"Run {run.id} {run.status}: {run.n_documents} documents, {run.n_topics} topics."
    )


@app.command("research")
def research_command(
    query: str = typer.Argument(
        None, help="Optional focus query; defaults to the configured domain seeds"
    ),
    rounds: int = typer.Option(None, help="Override RESEARCH_MAX_ROUNDS"),
    max_docs: int = typer.Option(None, help="Override RESEARCH_MAX_DOCS"),
    per_query: int = typer.Option(None, help="Override RESEARCH_PER_QUERY_LIMIT"),
    language: str = typer.Option(None, help="Output language: en | de (overrides .env)"),
    use_feedback: bool = typer.Option(
        True, help="Seed/steer the crawl from prior expert feedback"
    ),
) -> None:
    """Run a bounded deep-research crawl across all sources, then the full pipeline.

    This is also the command to schedule for the weekly monitoring run (project plan
    §6.3), e.g. via cron: ``0 6 * * 1 cd /path/to/backend && uv run trendscout research``.
    """
    from app.research.service import run_deep_research

    settings = get_settings()
    init_db()

    with Session(get_engine()) as session:
        outcome = run_deep_research(
            session=session,
            seeds=[query] if query else None,
            settings=settings,
            language=language,
            use_feedback=use_feedback,
            max_rounds=rounds,
            max_docs=max_docs,
            per_query_limit=per_query,
        )
    run = outcome.run
    typer.echo(
        f"Crawl: {run.n_documents} docs in {outcome.rounds} round(s), "
        f"{len(outcome.queries_used)} queries across {settings.sources}."
    )
    typer.echo(
        f"Run {run.id} {run.status}: {run.n_documents} documents, {run.n_topics} topics."
    )


@app.command("serve")
def serve_command(
    host: str = "127.0.0.1", port: int = 8000, reload: bool = False
) -> None:
    """Start the FastAPI server."""
    import uvicorn

    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
