"""Command-line interface for the trendscout backend."""

from __future__ import annotations

import typer
from sqlmodel import Session

from app.config import get_settings
from app.db import get_engine, init_db
from app.pipeline.run import run_pipeline

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
) -> None:
    """Run one full pipeline (ingest -> embed -> topics -> describe -> persist)."""
    init_db()
    with Session(get_engine()) as session:
        run = run_pipeline(query, session=session, limit=limit)
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
    use_feedback: bool = typer.Option(
        True, help="Seed/steer the crawl from prior expert feedback"
    ),
) -> None:
    """Run a bounded deep-research crawl across all sources, then the full pipeline."""
    from app.ingestion.registry import build_connectors
    from app.research.crawler import DeepResearchCrawler
    from app.research.expand import get_expander
    from app.research.feedback import (
        negative_terms_from_feedback,
        seeds_from_feedback,
    )
    from app.research.relevance import get_relevance
    from app.research.seeds import load_seeds, merge_seeds

    settings = get_settings()
    init_db()
    connectors = build_connectors(settings.source_list, settings)
    expander = get_expander(settings.expander)

    with Session(get_engine()) as session:
        base_seeds = [query] if query else load_seeds(settings)
        fb_seeds = seeds_from_feedback(session) if use_feedback else []
        excludes = negative_terms_from_feedback(session) if use_feedback else []
        seeds = merge_seeds(base_seeds, fb_seeds)

        relevance = get_relevance(
            settings.relevance,
            domain=settings.research_domain,
            include_terms=seeds,
            exclude_terms=excludes,
        )
        crawler = DeepResearchCrawler(
            connectors,
            expander=expander,
            relevance=relevance,
            domain=settings.research_domain,
            max_rounds=rounds or settings.research_max_rounds,
            max_docs=max_docs or settings.research_max_docs,
            per_query_limit=per_query or settings.research_per_query_limit,
            expand_terms=settings.research_expand_terms,
        )
        typer.echo(
            f"Crawling {len(seeds)} seed(s) across "
            f"{len(connectors)} source(s): {settings.sources}"
        )
        result = crawler.crawl(seeds)
        typer.echo(
            f"Crawl: {len(result.documents)} docs in {result.rounds} round(s), "
            f"{len(result.queries_used)} queries."
        )
        run = run_pipeline(
            settings.research_domain,
            session=session,
            raw_docs=result.documents,
            settings=settings,
            run_params={
                "mode": "deep_research",
                "sources": settings.source_list,
                "rounds": result.rounds,
                "queries_used": result.queries_used,
                "seeds": seeds,
            },
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
