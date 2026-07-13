"""API routes for runs, trends and expert feedback."""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from sqlmodel import Session, select

from app.db import get_engine, get_session
from app.evaluation import TrendLike, compute_overlap
from app.models import (
    MATURITY_LEVELS,
    CanonicalTrend,
    ExpertFeedback,
    ReferenceTrend,
    Run,
    RunEvent,
    Topic,
    TopicTimepoint,
    Trend,
    TrendAssessment,
    TrendDecision,
    TrendOccurrence,
    TrendTranslation,
)
from app.pestel import build_pestel_analysis
from app.portfolio import record_decision
from app.schemas import (
    EvaluationOut,
    FeedbackIn,
    FeedbackOut,
    OverlapMatch,
    PestelAnalysisOut,
    PortfolioDecisionIn,
    PortfolioTrendDetailOut,
    PortfolioTrendOut,
    ReferenceSummary,
    ReferenceTrendIn,
    ReferenceTrendOut,
    ReviewDecisionIn,
    ReviewQueueItemOut,
    RunDiffEntryOut,
    RunDiffOut,
    RunOut,
    RunProgressEventOut,
    RunProgressOut,
    RunRequest,
    SearchCapabilitiesOut,
    SearchSourceOut,
    SuggestedTrendOut,
    TimepointOut,
    TranslateIn,
    TranslateOut,
    TrendDecisionOut,
    TrendDetailOut,
    TrendEvidenceOut,
    TrendHistoryOut,
    TrendHistoryPointOut,
    TrendOut,
)

logger = logging.getLogger(__name__)

router = APIRouter()

DEPTH_PROFILES = {
    "quick": {"limit": 30, "rounds": 1, "per_query": 10},
    "standard": {"limit": 80, "rounds": 1, "per_query": 12},
    "deep": {"limit": 150, "rounds": 2, "per_query": 20},
}
TOPIC_GRANULARITY_PROFILES = {
    "compact": {"topic_max": 8, "min_cluster_size": 12},
    "balanced": {"topic_max": 12, "min_cluster_size": 8},
    "detailed": {"topic_max": 18, "min_cluster_size": 5},
}


def require_token(authorization: str | None = Header(default=None)) -> None:
    """Shared-token gate for state-changing routes. No-op when API_TOKEN is unset
    (local development); on non-local deployments set API_TOKEN to protect the
    billable / data-mutating endpoints."""
    from app.config import get_settings

    token = get_settings().api_token
    if not token:
        return
    if authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="Invalid or missing token")


def _run_pipeline_bg(
    run_id: int,
    keywords: list[str],
    query: str,
    limit: int,
    language: str = "en",
    mode: str = "deep_research",
    sources: list[str] | None = None,
    region: str = "global",
    depth: str = "deep",
    holistic_pestel: bool = True,
    topic_granularity: str = "balanced",
) -> None:
    """Execute a pipeline run in the background, with its own DB session.

    ``deep_research`` runs the bounded multi-source crawl (seeded by the keywords);
    ``simple`` does a single multi-source fetch for ``query``.
    """
    from app.config import get_settings
    from app.ingestion.registry import build_connectors
    from app.pipeline.progress import callback_for_run
    from app.research.planning import contextual_query, plan_deep_research_seeds
    from app.research.service import run_deep_research, run_simple_search

    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        if run is None:
            logger.error("background run %s no longer exists", run_id)
            return
        progress = callback_for_run(run_id)
        profile = DEPTH_PROFILES[depth]
        topic_profile = TOPIC_GRANULARITY_PROFILES[topic_granularity]
        settings = get_settings().model_copy(
            update={
                "topic_max": topic_profile["topic_max"],
                "bertopic_min_cluster_size": topic_profile["min_cluster_size"],
            }
        )
        connectors = build_connectors(sources, settings)
        try:
            if mode == "simple":
                run_simple_search(
                    contextual_query(query, region),
                    session=session,
                    connectors=connectors,
                    settings=settings,
                    language=language,
                    limit=limit,
                    run=run,
                    progress=progress,
                )
            else:
                seeds = plan_deep_research_seeds(
                    query=query,
                    keywords=keywords,
                    region=region,
                    holistic_pestel=holistic_pestel,
                )
                run_deep_research(
                    session=session,
                    seeds=seeds,
                    focus_query=query,
                    connectors=connectors,
                    settings=settings,
                    language=language,
                    max_rounds=profile["rounds"],
                    max_docs=limit,
                    per_query_limit=profile["per_query"],
                    run=run,
                    progress=progress,
                )
        except Exception as exc:
            logger.exception("background run failed")
            session.rollback()
            run = session.get(Run, run_id)
            if run is None:
                return
            if run.status != "failed":
                run.status = "failed"
                run.finished_at = datetime.now(UTC)
                run.error = f"{type(exc).__name__}: {exc}"[:500]
                session.add(run)
            session.commit()
            progress("failed", 100, "Run failed", {"error": run.error})


def _latest_completed_run_id(session: Session) -> int | None:
    run = session.exec(
        select(Run).where(Run.status == "completed").order_by(Run.id.desc())
    ).first()
    return run.id if run else None


def _to_trend_out(
    trend: Trend, topic: Topic, assessment: TrendAssessment | None
) -> TrendOut:
    return TrendOut(
        id=trend.id,
        run_id=trend.run_id,
        title=trend.title,
        summary=trend.summary,
        maturity=trend.maturity,
        emergence=trend.emergence,
        keywords=topic.keywords or [],
        size=topic.size,
        region=topic.region,
        country=topic.country,
        pestel=assessment.pestel if assessment else None,
        category=assessment.category if assessment else None,
        impact=assessment.impact if assessment else None,
        urgency=assessment.urgency if assessment else None,
        uncertainty=assessment.uncertainty if assessment else None,
        radar_stage=assessment.radar_stage if assessment else None,
    )


def _trends_with_relations(
    session: Session,
    run_id: int,
    *,
    maturity: str | None = None,
    region: str | None = None,
) -> list[tuple[Trend, Topic, TrendAssessment | None]]:
    """Fetch (Trend, Topic, TrendAssessment?) tuples in a single joined query,
    avoiding the previous 1 + 2N round-trips per trend."""
    query = (
        select(Trend, Topic, TrendAssessment)
        .join(Topic, Topic.id == Trend.topic_id)
        .outerjoin(TrendAssessment, TrendAssessment.trend_id == Trend.id)
        .where(Trend.run_id == run_id)
    )
    if maturity:
        query = query.where(Trend.maturity == maturity)
    if region:
        query = query.where(Topic.region == region)
    return session.exec(query).all()


def _decision_out(decision: TrendDecision) -> TrendDecisionOut:
    return TrendDecisionOut(
        id=decision.id,
        action=decision.action,
        reviewer=decision.reviewer,
        reason=decision.reason,
        created_at=decision.created_at,
        before=decision.before_values,
        after=decision.after_values,
    )


def _evidence_out(items: list[dict] | None, run_id: int) -> list[TrendEvidenceOut]:
    evidence: list[TrendEvidenceOut] = []
    for item in items or []:
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        published_at = item.get("published_at")
        evidence.append(
            TrendEvidenceOut(
                title=title,
                url=item.get("url"),
                source=item.get("source"),
                published_at=str(published_at) if published_at is not None else None,
                run_id=item.get("run_id", run_id),
            )
        )
    return evidence


def _snapshot_values(
    trend: Trend, topic: Topic, assessment: TrendAssessment | None
) -> dict[str, Any]:
    return {
        "title": trend.title,
        "summary": trend.summary,
        "maturity": trend.maturity,
        "emergence": trend.emergence,
        "keywords": topic.keywords or [],
        "size": topic.size,
        "region": topic.region,
        "country": topic.country,
        "pestel": assessment.pestel if assessment else None,
        "category": assessment.category if assessment else None,
        "impact": assessment.impact if assessment else None,
        "urgency": assessment.urgency if assessment else None,
        "uncertainty": assessment.uncertainty if assessment else None,
        "radar_stage": assessment.radar_stage if assessment else None,
    }


def _occurrence_snapshot(
    session: Session, occurrence: TrendOccurrence
) -> tuple[Trend, Topic, TrendAssessment | None] | None:
    return session.exec(
        select(Trend, Topic, TrendAssessment)
        .join(Topic, Topic.id == Trend.topic_id)
        .outerjoin(TrendAssessment, TrendAssessment.trend_id == Trend.id)
        .where(Trend.id == occurrence.trend_id)
    ).first()


def _latest_occurrences(
    session: Session, canonicals: list[CanonicalTrend]
) -> tuple[dict[str, TrendOccurrence], dict[str, int]]:
    ids = [canonical.id for canonical in canonicals]
    if not ids:
        return {}, {}
    occurrences = session.exec(
        select(TrendOccurrence)
        .where(TrendOccurrence.canonical_trend_id.in_(ids))
        .order_by(TrendOccurrence.run_id.desc(), TrendOccurrence.id.desc())
    ).all()
    latest: dict[str, TrendOccurrence] = {}
    counts: Counter[str] = Counter()
    for occurrence in occurrences:
        counts[occurrence.canonical_trend_id] += 1
        latest.setdefault(occurrence.canonical_trend_id, occurrence)
    return latest, dict(counts)


def _portfolio_out(
    canonical: CanonicalTrend,
    occurrence: TrendOccurrence,
    snapshot: tuple[Trend, Topic, TrendAssessment | None],
    occurrence_count: int,
) -> PortfolioTrendOut:
    trend, topic, _ = snapshot
    return PortfolioTrendOut(
        id=canonical.id,
        run_id=occurrence.run_id,
        title=canonical.title,
        summary=canonical.summary,
        maturity=canonical.maturity,
        emergence=trend.emergence,
        keywords=topic.keywords or [],
        size=topic.size,
        region=topic.region,
        country=topic.country,
        pestel=canonical.pestel,
        category=canonical.category,
        impact=canonical.impact,
        urgency=canonical.urgency,
        uncertainty=canonical.uncertainty,
        radar_stage=canonical.radar_stage,
        status=canonical.status,
        first_run_id=canonical.first_run_id,
        last_run_id=canonical.last_run_id,
        merged_into_id=canonical.merged_into_id,
        occurrence_count=occurrence_count,
        updated_at=canonical.updated_at,
    )


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/search/capabilities", response_model=SearchCapabilitiesOut)
def search_capabilities() -> SearchCapabilitiesOut:
    from app.config import get_settings

    settings = get_settings()
    firecrawl_ready = bool(settings.firecrawl_api_key)
    default_sources = [
        source
        for source in settings.source_list
        if source not in {"firecrawl", "firecrawl_web"} or firecrawl_ready
    ] or ["openalex"]
    return SearchCapabilitiesOut(
        sources=[
            SearchSourceOut(id="openalex", enabled=True),
            SearchSourceOut(id="arxiv", enabled=True),
            SearchSourceOut(
                id="firecrawl",
                enabled=firecrawl_ready,
                requires_configuration=not firecrawl_ready,
            ),
            SearchSourceOut(
                id="firecrawl_web",
                enabled=firecrawl_ready,
                requires_configuration=not firecrawl_ready,
            ),
        ],
        default_sources=default_sources,
        openai_enrichment=bool(settings.openai_api_key),
        topic_model=settings.topic_model,
        topic_granularities=list(TOPIC_GRANULARITY_PROFILES),
    )


@router.get("/runs", response_model=list[RunOut])
def list_runs(
    session: Session = Depends(get_session),
    limit: int = Query(default=20, ge=1, le=200),
) -> list[RunOut]:
    runs = list(session.exec(select(Run).order_by(Run.id.desc()).limit(limit)).all())
    run_ids = [run.id for run in runs]
    occurrences = (
        session.exec(
            select(TrendOccurrence).where(TrendOccurrence.run_id.in_(run_ids))
        ).all()
        if run_ids
        else []
    )
    changes: dict[int, Counter[str]] = {}
    reviews: dict[int, Counter[str]] = {}
    for occurrence in occurrences:
        changes.setdefault(occurrence.run_id, Counter())[occurrence.change_type] += 1
        reviews.setdefault(occurrence.run_id, Counter())[occurrence.review_status] += 1
    return [
        RunOut(
            id=run.id,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            n_documents=run.n_documents,
            n_topics=run.n_topics,
            embedder=run.embedder,
            topic_model=run.topic_model,
            describer=run.describer,
            params=run.params,
            error=run.error,
            change_counts=dict(changes.get(run.id, {})),
            review_counts=dict(reviews.get(run.id, {})),
        )
        for run in runs
    ]


@router.get("/runs/{run_id}/progress", response_model=RunProgressOut)
def get_run_progress(
    run_id: int, session: Session = Depends(get_session)
) -> RunProgressOut:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    events = list(
        session.exec(
            select(RunEvent)
            .where(RunEvent.run_id == run_id)
            .order_by(RunEvent.id)
        ).all()
    )
    latest = events[-1] if events else None
    return RunProgressOut(
        run_id=run.id,
        status=run.status,
        phase=latest.phase if latest else run.status,
        progress=latest.progress if latest else (100 if run.status != "running" else 0),
        message=latest.message if latest else "Run is waiting to start",
        n_documents=run.n_documents,
        n_topics=run.n_topics,
        error=run.error,
        events=[
            RunProgressEventOut(
                id=event.id,
                phase=event.phase,
                progress=event.progress,
                message=event.message,
                details=event.details,
                created_at=event.created_at,
            )
            for event in events
        ],
    )


@router.post("/runs", status_code=202, dependencies=[Depends(require_token)])
def start_run(
    body: RunRequest,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
) -> dict:
    """Kick off a real pipeline run from the UI (keyword search)."""
    from app.config import get_settings
    from app.pipeline.progress import record_run_event
    from app.pipeline.run import create_run

    keywords = [k.strip() for k in body.keywords if k.strip()]
    query = (body.query or "").strip() or " ".join(keywords)
    if not query:
        raise HTTPException(status_code=422, detail="keywords or query required")
    mode = body.mode
    settings = get_settings()
    profile = DEPTH_PROFILES[body.depth]
    topic_profile = TOPIC_GRANULARITY_PROFILES[body.topic_granularity]
    limit = body.limit or profile["limit"]
    available_sources = {"openalex", "arxiv"}
    if settings.firecrawl_api_key:
        available_sources.update({"firecrawl", "firecrawl_web"})
    default_sources = [
        source for source in settings.source_list if source in available_sources
    ] or ["openalex"]
    sources = list(dict.fromkeys(body.sources or default_sources))
    unavailable = [source for source in sources if source not in available_sources]
    if unavailable:
        raise HTTPException(
            status_code=422,
            detail=f"Sources are not configured: {', '.join(unavailable)}",
        )
    run_settings = settings.model_copy(
        update={
            "topic_max": topic_profile["topic_max"],
            "bertopic_min_cluster_size": topic_profile["min_cluster_size"],
        }
    )
    run = create_run(
        session,
        query=query,
        settings=run_settings,
        limit=limit,
        run_params={
            "mode": mode,
            "sources": sources,
            "keywords": keywords,
            "language": body.language,
            "region": body.region,
            "depth": body.depth,
            "holistic_pestel": body.holistic_pestel,
            "topic_granularity": body.topic_granularity,
            "topic_max": topic_profile["topic_max"],
            "bertopic_min_cluster_size": topic_profile["min_cluster_size"],
            "max_docs": limit,
            "max_rounds": profile["rounds"],
            "per_query_limit": profile["per_query"],
        },
    )
    record_run_event(
        run.id,
        "queued",
        2,
        "Run accepted and queued",
        {
            "query": query,
            "mode": mode,
            "sources": sources,
            "region": body.region,
            "depth": body.depth,
        },
    )
    background.add_task(
        _run_pipeline_bg,
        run.id,
        keywords,
        query,
        limit,
        body.language,
        mode,
        sources,
        body.region,
        body.depth,
        body.holistic_pestel,
        body.topic_granularity,
    )
    return {
        "status": "started",
        "run_id": run.id,
        "query": query,
        "language": body.language,
        "mode": mode,
        "started_at": run.started_at,
    }


@router.get("/trends", response_model=list[TrendOut])
def list_trends(
    run_id: int | None = Query(default=None, description="Defaults to latest run"),
    maturity: str | None = Query(default=None),
    region: str | None = Query(default=None, description="Filter by topic region"),
    session: Session = Depends(get_session),
) -> list[TrendOut]:
    if run_id is None:
        run_id = _latest_completed_run_id(session)
    if run_id is None:
        return []
    rows = _trends_with_relations(session, run_id, maturity=maturity, region=region)
    return [_to_trend_out(trend, topic, assessment) for trend, topic, assessment in rows]


@router.get("/trends/{trend_id}", response_model=TrendDetailOut)
def get_trend(
    trend_id: int, session: Session = Depends(get_session)
) -> TrendDetailOut:
    row = session.exec(
        select(Trend, Topic, TrendAssessment)
        .join(Topic, Topic.id == Trend.topic_id)
        .outerjoin(TrendAssessment, TrendAssessment.trend_id == Trend.id)
        .where(Trend.id == trend_id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Trend not found")
    trend, topic, assessment = row
    base = _to_trend_out(trend, topic, assessment)
    timepoints = session.exec(
        select(TopicTimepoint)
        .where(TopicTimepoint.topic_id == trend.topic_id)
        .order_by(TopicTimepoint.period)
    ).all()
    timepoints = timepoints[-24:]
    return TrendDetailOut(
        **base.model_dump(),
        rationale=assessment.rationale if assessment else None,
        evidence=trend.evidence or [],
        timeseries=[TimepointOut(period=t.period, doc_count=t.doc_count) for t in timepoints],
    )


@router.get("/portfolio/trends", response_model=list[PortfolioTrendOut])
def list_portfolio_trends(
    status: str | None = Query(default="active"),
    session: Session = Depends(get_session),
) -> list[PortfolioTrendOut]:
    query = select(CanonicalTrend).order_by(CanonicalTrend.updated_at.desc())
    if status:
        query = query.where(CanonicalTrend.status == status)
    canonicals = list(session.exec(query).all())
    latest, counts = _latest_occurrences(session, canonicals)
    result: list[PortfolioTrendOut] = []
    for canonical in canonicals:
        occurrence = latest.get(canonical.id)
        snapshot = _occurrence_snapshot(session, occurrence) if occurrence else None
        if occurrence and snapshot:
            result.append(_portfolio_out(canonical, occurrence, snapshot, counts[canonical.id]))
    return result


@router.get(
    "/portfolio/trends/{canonical_id}", response_model=PortfolioTrendDetailOut
)
def get_portfolio_trend(
    canonical_id: str, session: Session = Depends(get_session)
) -> PortfolioTrendDetailOut:
    canonical = session.get(CanonicalTrend, canonical_id)
    if canonical is None:
        raise HTTPException(status_code=404, detail="Portfolio trend not found")
    latest, counts = _latest_occurrences(session, [canonical])
    occurrence = latest.get(canonical.id)
    snapshot = _occurrence_snapshot(session, occurrence) if occurrence else None
    if occurrence is None or snapshot is None:
        raise HTTPException(status_code=404, detail="Portfolio trend has no snapshot")
    trend, topic, assessment = snapshot
    base = _portfolio_out(canonical, occurrence, snapshot, counts[canonical.id])
    timepoints = session.exec(
        select(TopicTimepoint)
        .where(TopicTimepoint.topic_id == topic.id)
        .order_by(TopicTimepoint.period)
    ).all()
    timepoints = timepoints[-24:]
    return PortfolioTrendDetailOut(
        **base.model_dump(),
        rationale=assessment.rationale if assessment else None,
        evidence=_evidence_out(trend.evidence, occurrence.run_id),
        timeseries=[
            TimepointOut(period=point.period, doc_count=point.doc_count)
            for point in timepoints
        ],
    )


@router.get(
    "/portfolio/trends/{canonical_id}/pestel-analysis",
    response_model=PestelAnalysisOut,
)
def get_portfolio_trend_pestel_analysis(
    canonical_id: str, session: Session = Depends(get_session)
) -> PestelAnalysisOut:
    canonical = session.get(CanonicalTrend, canonical_id)
    if canonical is None:
        raise HTTPException(status_code=404, detail="Portfolio trend not found")
    occurrence = session.exec(
        select(TrendOccurrence)
        .where(TrendOccurrence.canonical_trend_id == canonical_id)
        .order_by(TrendOccurrence.run_id.desc(), TrendOccurrence.id.desc())
    ).first()
    if occurrence is None:
        raise HTTPException(status_code=404, detail="Portfolio trend has no snapshot")
    try:
        return build_pestel_analysis(
            session,
            canonical_id=canonical_id,
            occurrence=occurrence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/portfolio/trends/{canonical_id}/history", response_model=TrendHistoryOut
)
def get_portfolio_trend_history(
    canonical_id: str, session: Session = Depends(get_session)
) -> TrendHistoryOut:
    if session.get(CanonicalTrend, canonical_id) is None:
        raise HTTPException(status_code=404, detail="Portfolio trend not found")
    occurrences = session.exec(
        select(TrendOccurrence)
        .where(TrendOccurrence.canonical_trend_id == canonical_id)
        .order_by(TrendOccurrence.run_id, TrendOccurrence.id)
    ).all()
    points: list[TrendHistoryPointOut] = []
    evidence: list[TrendEvidenceOut] = []
    for occurrence in occurrences:
        snapshot = _occurrence_snapshot(session, occurrence)
        if snapshot is None:
            continue
        trend, topic, assessment = snapshot
        points.append(
            TrendHistoryPointOut(
                run_id=occurrence.run_id,
                occurred_at=occurrence.created_at,
                maturity=trend.maturity,
                impact=assessment.impact if assessment else None,
                urgency=assessment.urgency if assessment else None,
                uncertainty=assessment.uncertainty if assessment else None,
                emergence=trend.emergence,
                size=topic.size,
                change_type=occurrence.change_type,
            )
        )
        evidence.extend(_evidence_out(trend.evidence, occurrence.run_id))
    decisions = session.exec(
        select(TrendDecision)
        .where(TrendDecision.canonical_trend_id == canonical_id)
        .order_by(TrendDecision.created_at, TrendDecision.id)
    ).all()
    return TrendHistoryOut(
        trend_id=canonical_id,
        points=points,
        evidence=evidence,
        decisions=[_decision_out(decision) for decision in decisions],
    )


@router.get("/runs/{run_id}/diff", response_model=RunDiffOut)
def get_run_diff(run_id: int, session: Session = Depends(get_session)) -> RunDiffOut:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    occurrences = session.exec(
        select(TrendOccurrence)
        .where(TrendOccurrence.run_id == run_id)
        .order_by(TrendOccurrence.id)
    ).all()
    entries: list[RunDiffEntryOut] = []
    for occurrence in occurrences:
        snapshot = _occurrence_snapshot(session, occurrence)
        if snapshot is None:
            continue
        trend, topic, assessment = snapshot
        previous = session.exec(
            select(TrendOccurrence)
            .where(
                TrendOccurrence.canonical_trend_id == occurrence.canonical_trend_id,
                TrendOccurrence.run_id < occurrence.run_id,
            )
            .order_by(TrendOccurrence.run_id.desc(), TrendOccurrence.id.desc())
        ).first() if occurrence.canonical_trend_id is not None else None
        previous_snapshot = _occurrence_snapshot(session, previous) if previous else None
        entries.append(
            RunDiffEntryOut(
                occurrence_id=occurrence.id,
                canonical_trend_id=occurrence.canonical_trend_id,
                trend_id=occurrence.trend_id,
                title=trend.title,
                change_type=occurrence.change_type,
                match_score=occurrence.match_score,
                margin=occurrence.match_margin,
                changed_fields=occurrence.changed_fields or [],
                review_status=occurrence.review_status,
                review_reasons=occurrence.review_reasons or [],
                evidence_added_count=occurrence.evidence_added_count,
                evidence_removed_count=occurrence.evidence_removed_count,
                prevalence=occurrence.prevalence,
                before=_snapshot_values(*previous_snapshot) if previous_snapshot else None,
                after=_snapshot_values(trend, topic, assessment),
            )
        )
    counted = Counter(entry.change_type for entry in entries)
    return RunDiffOut(
        run_id=run_id,
        started_at=run.started_at,
        query=(run.params or {}).get("query"),
        counts={
            "new": counted["new"],
            "classification_changed": counted["classification_changed"],
            "content_changed": counted["content_changed"],
            "evidence_only": counted["evidence_only"],
            "unchanged": counted["unchanged"],
        },
        entries=entries,
    )


@router.get("/review-queue", response_model=list[ReviewQueueItemOut])
def list_review_queue(
    run_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[ReviewQueueItemOut]:
    query = (
        select(TrendOccurrence, Trend, CanonicalTrend)
        .join(Trend, Trend.id == TrendOccurrence.trend_id)
        .outerjoin(
            CanonicalTrend, CanonicalTrend.id == TrendOccurrence.canonical_trend_id
        )
        .where(TrendOccurrence.review_status == "pending")
        .order_by(TrendOccurrence.run_id.desc(), TrendOccurrence.id.desc())
    )
    if run_id is not None:
        query = query.where(TrendOccurrence.run_id == run_id)
    rows = session.exec(query).all()
    return [
        ReviewQueueItemOut(
            occurrence_id=occurrence.id,
            run_id=occurrence.run_id,
            canonical_trend_id=canonical.id if canonical else None,
            title=trend.title,
            summary=trend.summary,
            maturity=trend.maturity,
            match_score=occurrence.match_score,
            margin=occurrence.match_margin,
            change_type=occurrence.change_type,
            review_status=occurrence.review_status,
            review_reasons=occurrence.review_reasons or [],
            changed_fields=occurrence.changed_fields or [],
            evidence_added_count=occurrence.evidence_added_count,
            evidence_removed_count=occurrence.evidence_removed_count,
            prevalence=occurrence.prevalence,
            reason=occurrence.review_reason,
            suggested_trend=(
                SuggestedTrendOut(
                    id=canonical.id, title=canonical.title, status=canonical.status
                )
                if canonical
                else None
            ),
        )
        for occurrence, trend, canonical in rows
    ]


@router.post(
    "/portfolio/trends/{canonical_id}/decisions",
    response_model=TrendDecisionOut,
    dependencies=[Depends(require_token)],
)
def decide_portfolio_trend(
    canonical_id: str,
    body: PortfolioDecisionIn,
    session: Session = Depends(get_session),
) -> TrendDecisionOut:
    values = dict(body.changes)
    if body.action == "merge":
        target_id = str(body.target_trend_id) if body.target_trend_id is not None else None
        if target_id == canonical_id:
            raise HTTPException(status_code=422, detail="A trend cannot be merged into itself")
        values["merged_into_id"] = target_id
    try:
        decision = record_decision(
            session,
            canonical_trend_id=canonical_id,
            action=body.action,
            reviewer=body.reviewer,
            reason=body.reason,
            values=values,
            idempotency_key=body.idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _decision_out(decision)


@router.post(
    "/review-queue/{occurrence_id}/decision",
    response_model=TrendDecisionOut,
    dependencies=[Depends(require_token)],
)
def decide_review_item(
    occurrence_id: int,
    body: ReviewDecisionIn,
    session: Session = Depends(get_session),
) -> TrendDecisionOut:
    existing = session.exec(
        select(TrendDecision).where(
            TrendDecision.idempotency_key == body.idempotency_key
        )
    ).first()
    if existing:
        return _decision_out(existing)
    occurrence = session.get(TrendOccurrence, occurrence_id)
    if occurrence is None:
        raise HTTPException(status_code=404, detail="Review occurrence not found")
    if occurrence.review_status != "pending":
        raise HTTPException(status_code=409, detail="Review occurrence is already resolved")
    snapshot = _occurrence_snapshot(session, occurrence)
    if snapshot is None:
        raise HTTPException(status_code=409, detail="Occurrence snapshot is unavailable")
    trend, _, assessment = snapshot
    canonical_id = occurrence.canonical_trend_id
    proposed = {
        "title": trend.title,
        "summary": trend.summary,
        "maturity": trend.maturity,
        "pestel": assessment.pestel if assessment else None,
        "category": assessment.category if assessment else None,
        "impact": assessment.impact if assessment else None,
        "urgency": assessment.urgency if assessment else None,
        "uncertainty": assessment.uncertainty if assessment else None,
        "radar_stage": assessment.radar_stage if assessment else None,
    }
    reason_kinds = {
        reason.get("kind")
        for reason in (occurrence.review_reasons or [])
        if isinstance(reason, dict)
    }
    identity_conflict = "identity" in reason_kinds
    allowed = (
        {"link", "create", "merge", "reject"}
        if identity_conflict
        else {"confirm", "correct", "reject"}
    )
    if body.action not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Action {body.action} is not valid for this review type",
        )

    values: dict[str, Any] = {}
    if body.action in {"link", "merge"}:
        requested_id = body.canonical_trend_id or body.target_trend_id
        if requested_id is None:
            raise HTTPException(status_code=422, detail="Target trend is required")
        target_id = str(requested_id)
        if target_id == canonical_id and body.action == "merge":
            raise HTTPException(status_code=422, detail="A trend cannot be merged into itself")
        if session.get(CanonicalTrend, target_id) is None:
            raise HTTPException(status_code=422, detail="Target trend does not exist")
        if body.action == "link":
            occurrence.canonical_trend_id = target_id
            canonical_id = target_id
            values = proposed
        else:
            values["merged_into_id"] = target_id
    elif body.action == "create":
        canonical_id = str(uuid.uuid4())
        canonical = CanonicalTrend(
            id=canonical_id,
            status="active",
            title=trend.title,
            summary=trend.summary,
            maturity=trend.maturity,
            pestel=assessment.pestel if assessment else None,
            category=assessment.category if assessment else None,
            impact=assessment.impact if assessment else None,
            urgency=assessment.urgency if assessment else None,
            uncertainty=assessment.uncertainty if assessment else None,
            radar_stage=assessment.radar_stage if assessment else None,
            first_run_id=occurrence.run_id,
            last_run_id=occurrence.run_id,
        )
        session.add(canonical)
        session.flush()
        occurrence.canonical_trend_id = canonical_id
        values = proposed
    elif body.action in {"confirm", "correct"}:
        values = proposed
        if body.action == "correct":
            values.update(body.changes)
        if canonical_id is None:
            canonical_id = str(uuid.uuid4())
            session.add(
                CanonicalTrend(
                    id=canonical_id,
                    status="review",
                    title=trend.title,
                    summary=trend.summary,
                    maturity=trend.maturity,
                    pestel=assessment.pestel if assessment else None,
                    category=assessment.category if assessment else None,
                    impact=assessment.impact if assessment else None,
                    urgency=assessment.urgency if assessment else None,
                    uncertainty=assessment.uncertainty if assessment else None,
                    radar_stage=assessment.radar_stage if assessment else None,
                    first_run_id=occurrence.run_id,
                    last_run_id=occurrence.run_id,
                )
            )
            occurrence.canonical_trend_id = canonical_id
            session.flush()

    occurrence.review_status = "rejected" if body.action == "reject" else "approved"
    session.add(occurrence)
    session.flush()
    if body.action == "reject" and canonical_id is None:
        decision = TrendDecision(
            canonical_trend_id=None,
            occurrence_id=occurrence.id,
            action="reject",
            reviewer=body.reviewer,
            reason=body.reason,
            before_values=None,
            after_values={"review_status": "rejected"},
            idempotency_key=body.idempotency_key,
        )
        session.add(decision)
        session.commit()
        session.refresh(decision)
        return _decision_out(decision)
    if canonical_id is None:
        raise HTTPException(status_code=409, detail="Review identity is unavailable")
    canonical = session.get(CanonicalTrend, canonical_id)
    if canonical and body.action != "reject":
        canonical.last_run_id = occurrence.run_id
        session.add(canonical)
    try:
        decision = record_decision(
            session,
            canonical_trend_id=canonical_id,
            occurrence_id=occurrence.id,
            action=body.action,
            reviewer=body.reviewer,
            reason=body.reason,
            values=values,
            idempotency_key=body.idempotency_key,
        )
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if body.action == "merge":
        occurrence.canonical_trend_id = str(values["merged_into_id"])
        session.add(occurrence)
        session.commit()
    return _decision_out(decision)


@router.post(
    "/trends/{trend_id}/feedback",
    response_model=FeedbackOut,
    dependencies=[Depends(require_token)],
)
def add_feedback(
    trend_id: int, body: FeedbackIn, session: Session = Depends(get_session)
) -> ExpertFeedback:
    trend = session.get(Trend, trend_id)
    if not trend:
        raise HTTPException(status_code=404, detail="Trend not found")
    # A maturity correction is the authoritative assessment: apply it to the trend so
    # it survives reload. The machine value is preserved in ExpertFeedback.old_value.
    if body.action == "correct" and body.field == "maturity":
        if body.new_value not in MATURITY_LEVELS:
            raise HTTPException(status_code=422, detail="invalid maturity value")
        trend.maturity = body.new_value
        session.add(trend)
    feedback = ExpertFeedback(
        trend_id=trend_id,
        action=body.action,
        field=body.field,
        old_value=body.old_value,
        new_value=body.new_value,
        comment=body.comment,
    )
    session.add(feedback)
    session.commit()
    session.refresh(feedback)
    return feedback


@router.post(
    "/trends/{trend_id}/translate",
    response_model=TranslateOut,
    dependencies=[Depends(require_token)],
)
def translate_trend(
    trend_id: int, body: TranslateIn, session: Session = Depends(get_session)
) -> TranslateOut:
    """Translate a trend's title/summary/rationale into ``language`` on demand (ADR-28)."""
    from app.config import get_settings
    from app.pipeline.translate import resolve_translator

    trend = session.get(Trend, trend_id)
    if not trend:
        raise HTTPException(status_code=404, detail="Trend not found")

    # Trend text is immutable per run, so a translation can be cached: a repeated
    # "show translation" toggle must not re-buy the same paid LLM call.
    cached = session.exec(
        select(TrendTranslation).where(
            TrendTranslation.trend_id == trend.id,
            TrendTranslation.language == body.language,
        )
    ).first()
    if cached:
        return TranslateOut(
            language=cached.language,
            title=cached.title,
            summary=cached.summary,
            rationale=cached.rationale,
        )

    assessment = session.exec(
        select(TrendAssessment).where(TrendAssessment.trend_id == trend.id)
    ).first()

    translator = resolve_translator(get_settings())
    result = translator.translate(
        title=trend.title,
        summary=trend.summary,
        rationale=assessment.rationale if assessment else None,
        language=body.language,
    )
    session.add(
        TrendTranslation(
            trend_id=trend.id,
            language=body.language,
            title=result.title,
            summary=result.summary,
            rationale=result.rationale,
        )
    )
    session.commit()
    return TranslateOut(
        language=body.language,
        title=result.title,
        summary=result.summary,
        rationale=result.rationale,
    )


@router.get("/reference-trends", response_model=list[ReferenceTrendOut])
def list_reference_trends(
    session: Session = Depends(get_session),
) -> list[ReferenceTrend]:
    return session.exec(
        select(ReferenceTrend).order_by(ReferenceTrend.id.desc())
    ).all()


@router.post(
    "/reference-trends",
    response_model=ReferenceTrendOut,
    status_code=201,
    dependencies=[Depends(require_token)],
)
def create_reference_trend(
    body: ReferenceTrendIn, session: Session = Depends(get_session)
) -> ReferenceTrend:
    """Register a manually-identified trend as part of the evaluation baseline."""
    if not body.title.strip():
        raise HTTPException(status_code=422, detail="title required")
    ref = ReferenceTrend(
        title=body.title.strip(),
        keywords=[k.strip() for k in body.keywords if k.strip()],
        pestel=body.pestel,
        category=body.category,
        note=body.note,
    )
    session.add(ref)
    session.commit()
    session.refresh(ref)
    return ref


@router.delete(
    "/reference-trends/{ref_id}",
    status_code=204,
    dependencies=[Depends(require_token)],
)
def delete_reference_trend(
    ref_id: int, session: Session = Depends(get_session)
) -> None:
    ref = session.get(ReferenceTrend, ref_id)
    if not ref:
        raise HTTPException(status_code=404, detail="Reference trend not found")
    session.delete(ref)
    session.commit()


@router.get("/evaluation/overlap", response_model=EvaluationOut)
def evaluation_overlap(
    run_id: int | None = Query(default=None, description="Defaults to latest run"),
    threshold: float = Query(default=0.18, ge=0.0, le=1.0),
    session: Session = Depends(get_session),
) -> EvaluationOut:
    """Compare a run's discovered trends to the manual reference list (§11)."""
    if run_id is None:
        run_id = _latest_completed_run_id(session)

    trends: list[TrendLike] = []
    if run_id is not None:
        rows = session.exec(
            select(Trend, Topic)
            .join(Topic, Topic.id == Trend.topic_id)
            .where(Trend.run_id == run_id)
        ).all()
        for trend, topic in rows:
            trends.append(
                TrendLike(
                    id=trend.id,
                    title=trend.title,
                    keywords=topic.keywords or [],
                )
            )

    references = [
        TrendLike(id=r.id, title=r.title, keywords=r.keywords or [])
        for r in session.exec(select(ReferenceTrend)).all()
    ]

    result = compute_overlap(trends, references, threshold=threshold)
    return EvaluationOut(
        run_id=run_id,
        n_references=result.n_references,
        n_trends=result.n_trends,
        matched_references=result.n_matched_references,
        precision=round(result.precision, 3),
        recall=round(result.recall, 3),
        threshold=result.threshold,
        matches=[OverlapMatch(**vars(m)) for m in result.matches],
        missed_references=[
            ReferenceSummary(id=r.id, title=r.title) for r in result.missed_references
        ],
        novel_trends=[
            ReferenceSummary(id=t.id, title=t.title) for t in result.novel_trends
        ],
    )
