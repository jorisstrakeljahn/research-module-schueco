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

from sqlmodel import Session

from app.config import Settings, get_settings
from app.ingestion.base import Connector, RawDocument
from app.models import Run
from app.pipeline.run import run_pipeline
from app.research.crawler import DeepResearchCrawler
from app.research.expand import get_expander
from app.research.feedback import negative_terms_from_feedback, seeds_from_feedback
from app.research.relevance import get_relevance
from app.research.seeds import load_seeds, merge_seeds

logger = logging.getLogger(__name__)


@dataclass
class ResearchOutcome:
    """Result of a research run: the persisted Run plus crawl bookkeeping."""

    run: Run
    seeds: list[str]
    queries_used: list[str]
    rounds: int


def _dedupe(raw_docs: list[RawDocument]) -> list[RawDocument]:
    seen: set[str] = set()
    unique: list[RawDocument] = []
    for doc in raw_docs:
        key = (doc.external_id or doc.url or doc.title or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(doc)
    return unique


def run_simple_search(
    query: str,
    *,
    session: Session,
    connectors: list[Connector] | None = None,
    settings: Settings | None = None,
    language: str | None = None,
    limit: int | None = None,
) -> Run:
    """Fetch ``query`` once from every enabled connector, then run the full pipeline."""
    from app.ingestion.registry import build_connectors

    settings = settings or get_settings()
    connectors = connectors if connectors is not None else build_connectors(
        settings.source_list, settings
    )
    per_limit = limit or settings.research_per_query_limit

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
    raw_docs = _dedupe(fetched)

    return run_pipeline(
        query,
        session=session,
        raw_docs=raw_docs,
        settings=settings,
        language=language,
        run_params={"mode": "simple", "sources": settings.source_list},
    )


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
) -> ResearchOutcome:
    """Run a bounded deep-research crawl across all sources, then the full pipeline."""
    from app.ingestion.registry import build_connectors

    settings = settings or get_settings()
    connectors = connectors if connectors is not None else build_connectors(
        settings.source_list, settings
    )
    expander = get_expander(settings.expander)

    base_seeds = [s for s in (seeds or []) if s and s.strip()] or load_seeds(settings)
    fb_seeds = seeds_from_feedback(session) if use_feedback else []
    excludes = negative_terms_from_feedback(session) if use_feedback else []
    merged = merge_seeds(base_seeds, fb_seeds)

    relevance = get_relevance(
        settings.relevance,
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
    result = crawler.crawl(merged)

    run = run_pipeline(
        focus_query or settings.research_domain,
        session=session,
        raw_docs=result.documents,
        settings=settings,
        language=language,
        run_params={
            "mode": "deep_research",
            "sources": settings.source_list,
            "rounds": result.rounds,
            "queries_used": result.queries_used,
            "seeds": merged,
        },
    )
    return ResearchOutcome(
        run=run,
        seeds=merged,
        queries_used=result.queries_used,
        rounds=result.rounds,
    )
