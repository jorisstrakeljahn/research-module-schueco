"""Research orchestration shared by the CLI and the HTTP API.

Two entry points wrap :func:`~app.pipeline.run.run_pipeline` so the same behaviour is
available from ``trendscout research`` (CLI) and from ``POST /runs`` (UI button):

* :func:`run_simple_search` — one fetch per enabled connector for a single query
  (fast, cheap, deterministic). The lightweight path for ad-hoc lookups.
* :func:`run_deep_research` — the bounded focused crawl (multi-source, relevance gate,
  query expansion, expert-feedback steering) described in ADR-22/23/24.

Keeping this wiring in one place avoids the previous drift where the API only ever hit
OpenAlex while the real pipeline lived in the CLI.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlmodel import Session

from app.config import Settings, get_settings
from app.ingestion.base import Connector, RawDocument, dedupe
from app.models import Run
from app.pipeline.progress import ProgressCallback
from app.pipeline.run import create_run, run_pipeline
from app.research.crawler import DeepResearchCrawler
from app.research.expand import get_expander
from app.research.feedback import (
    negative_terms_from_feedback,
    seeds_from_feedback,
    seeds_from_portfolio,
)
from app.research.relevance import get_relevance
from app.research.seeds import load_seeds, merge_seeds

logger = logging.getLogger(__name__)


def _mark_failed(session: Session, run: Run, exc: Exception) -> None:
    session.rollback()
    run.status = "failed"
    run.finished_at = datetime.now(UTC)
    run.error = f"{type(exc).__name__}: {exc}"[:500]
    session.add(run)
    session.commit()


@dataclass
class ResearchOutcome:
    """Result of a research run: the persisted Run plus crawl bookkeeping."""

    run: Run
    seeds: list[str]
    queries_used: list[str]
    rounds: int


def run_simple_search(
    query: str,
    *,
    session: Session,
    connectors: list[Connector] | None = None,
    settings: Settings | None = None,
    language: str | None = None,
    limit: int | None = None,
    run: Run | None = None,
    progress: ProgressCallback | None = None,
) -> Run:
    """Fetch ``query`` once from every enabled connector, then run the full pipeline."""
    from app.ingestion.registry import build_connectors

    settings = settings or get_settings()
    connectors = connectors if connectors is not None else build_connectors(
        settings.source_list, settings
    )
    source_names = list(dict.fromkeys(connector.source_name for connector in connectors))
    per_limit = limit or settings.research_per_query_limit
    run = run or create_run(
        session,
        query=query,
        settings=settings,
        limit=per_limit,
        run_params={"mode": "simple", "sources": source_names},
    )

    try:
        if progress:
            progress(
                "researching",
                10,
                "Connected sources are being searched",
                {"sources": source_names},
            )
        fetched: list[RawDocument] = []
        for connector in connectors:
            try:
                fetched.extend(connector.fetch(query, limit=per_limit))
            except Exception:
                logger.warning(
                    "Connector %s failed for query %r; skipping",
                    getattr(connector, "source_name", type(connector).__name__),
                    query,
                    exc_info=True,
                )
                continue
        raw_docs = dedupe(fetched)
        if progress:
            progress(
                "researching",
                25,
                "Source search completed",
                {"findings": len(raw_docs)},
            )

        return run_pipeline(
            query,
            session=session,
            raw_docs=raw_docs,
            settings=settings,
            language=language,
            run=run,
            progress=progress,
        )
    except Exception as exc:
        if run.status != "failed":
            _mark_failed(session, run, exc)
        raise


def run_deep_research(
    *,
    session: Session,
    seeds: list[str] | None = None,
    focus_query: str | None = None,
    settings: Settings | None = None,
    language: str | None = None,
    use_feedback: bool = True,
    max_rounds: int | None = None,
    max_docs: int | None = None,
    per_query_limit: int | None = None,
    connectors: list[Connector] | None = None,
    run: Run | None = None,
    progress: ProgressCallback | None = None,
) -> ResearchOutcome:
    """Run a bounded deep-research crawl across all sources, then the full pipeline."""
    from app.ingestion.registry import build_connectors

    settings = settings or get_settings()
    connectors = connectors if connectors is not None else build_connectors(
        settings.source_list, settings
    )
    source_names = list(dict.fromkeys(connector.source_name for connector in connectors))
    expander = get_expander(settings.expander)

    base_seeds = [s for s in (seeds or []) if s and s.strip()] or load_seeds(settings)
    portfolio_seeds = seeds_from_portfolio(session)
    fb_seeds = seeds_from_feedback(session) if use_feedback else []
    excludes = negative_terms_from_feedback(session) if use_feedback else []
    merged = merge_seeds(base_seeds, portfolio_seeds, fb_seeds)

    # Expert rejections only take effect through an active relevance gate. With the
    # default RELEVANCE=off (PassthroughRelevance) they would be silently ignored, so
    # escalate to the keyword gate whenever there are exclusion terms to honor.
    relevance_name = settings.relevance
    if relevance_name == "off" and excludes:
        relevance_name = "keyword"
        logger.info(
            "Escalating relevance gate to 'keyword' to honor %d rejection term(s)",
            len(excludes),
        )
    relevance = get_relevance(
        relevance_name,
        domain=settings.research_domain,
        include_terms=merged,
        exclude_terms=excludes,
    )
    crawler = DeepResearchCrawler(
        connectors,
        expander=expander,
        relevance=relevance,
        domain=settings.research_domain,
        max_rounds=max_rounds or settings.research_max_rounds,
        max_docs=max_docs or settings.research_max_docs,
        per_query_limit=per_query_limit or settings.research_per_query_limit,
        expand_terms=settings.research_expand_terms,
    )
    query = focus_query or settings.research_domain
    run_params = {
        "mode": "deep_research",
        "sources": source_names,
        "seeds": merged,
    }
    run = run or create_run(
        session,
        query=query,
        settings=settings,
        limit=max_docs or settings.research_max_docs,
        run_params=run_params,
    )
    try:
        if progress:
            progress(
                "researching",
                8,
                "Deep research is expanding and evaluating search queries",
                {"sources": source_names, "seeds": merged},
            )
        result = crawler.crawl(merged)
        if progress:
            progress(
                "researching",
                25,
                "Deep research crawl completed",
                {
                    "findings": len(result.documents),
                    "rounds": result.rounds,
                    "queries": len(result.queries_used),
                },
            )

        run.params = {
            **(run.params or {}),
            "rounds": result.rounds,
            "queries_used": result.queries_used,
        }
        session.add(run)
        session.commit()
        run = run_pipeline(
            query,
            session=session,
            raw_docs=result.documents,
            settings=settings,
            language=language,
            run=run,
            progress=progress,
        )
    except Exception as exc:
        if run.status != "failed":
            _mark_failed(session, run, exc)
        raise
    return ResearchOutcome(
        run=run,
        seeds=merged,
        queries_used=result.queries_used,
        rounds=result.rounds,
    )
