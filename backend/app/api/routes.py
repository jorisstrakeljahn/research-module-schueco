"""API routes for runs, trends and expert feedback."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.db import get_engine, get_session
from app.evaluation import TrendLike, compute_overlap
from app.models import (
    MATURITY_LEVELS,
    ExpertFeedback,
    ReferenceTrend,
    Run,
    Topic,
    TopicTimepoint,
    Trend,
    TrendAssessment,
)
from app.schemas import (
    EvaluationOut,
    FeedbackIn,
    FeedbackOut,
    OverlapMatch,
    ReferenceSummary,
    ReferenceTrendIn,
    ReferenceTrendOut,
    RunOut,
    RunRequest,
    TimepointOut,
    TranslateIn,
    TranslateOut,
    TrendDetailOut,
    TrendOut,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _run_pipeline_bg(
    keywords: list[str],
    query: str,
    limit: int,
    language: str = "en",
    mode: str = "deep_research",
) -> None:
    """Execute a pipeline run in the background, with its own DB session.

    ``deep_research`` runs the bounded multi-source crawl (seeded by the keywords);
    ``simple`` does a single multi-source fetch for ``query``.
    """
    from app.research.service import run_deep_research, run_simple_search

    with Session(get_engine()) as session:
        try:
            if mode == "simple":
                run_simple_search(
                    query, session=session, language=language, limit=limit
                )
            else:
                run_deep_research(
                    session=session,
                    seeds=keywords or [query],
                    focus_query=query,
                    language=language,
                )
        except Exception as exc:
            # For deep research the Run row is created only after the crawl, so a
            # pre-Run crawl failure would otherwise leave no trace to poll. Persist a
            # terminal failed Run so every background invocation is observable.
            logger.exception("background run failed")
            session.rollback()
            session.add(
                Run(
                    status="failed",
                    finished_at=datetime.now(UTC),
                    error=f"{type(exc).__name__}: {exc}"[:500],
                    params={"query": query, "mode": mode},
                )
            )
            session.commit()


def _latest_completed_run_id(session: Session) -> int | None:
    run = session.exec(
        select(Run).where(Run.status == "completed").order_by(Run.id.desc())
    ).first()
    return run.id if run else None


def _trend_to_out(session: Session, trend: Trend) -> TrendOut:
    topic = session.get(Topic, trend.topic_id)
    assessment = session.exec(
        select(TrendAssessment).where(TrendAssessment.trend_id == trend.id)
    ).first()
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


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/runs", response_model=list[RunOut])
def list_runs(
    session: Session = Depends(get_session),
    limit: int = Query(default=20, ge=1, le=200),
) -> list[Run]:
    return session.exec(select(Run).order_by(Run.id.desc()).limit(limit)).all()


@router.post("/runs", status_code=202)
def start_run(body: RunRequest, background: BackgroundTasks) -> dict:
    """Kick off a real pipeline run from the UI (keyword search)."""
    keywords = [k.strip() for k in body.keywords if k.strip()]
    query = " ".join(keywords) or (body.query or "").strip()
    if not query:
        raise HTTPException(status_code=422, detail="keywords or query required")
    mode = body.mode if body.mode in ("simple", "deep_research") else "deep_research"
    background.add_task(
        _run_pipeline_bg, keywords, query, body.limit, body.language, mode
    )
    return {
        "status": "started",
        "query": query,
        "language": body.language,
        "mode": mode,
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
    query = select(Trend).where(Trend.run_id == run_id)
    if maturity:
        query = query.where(Trend.maturity == maturity)
    if region:
        query = query.join(Topic, Topic.id == Trend.topic_id).where(
            Topic.region == region
        )
    trends = session.exec(query).all()
    return [_trend_to_out(session, t) for t in trends]


@router.get("/trends/{trend_id}", response_model=TrendDetailOut)
def get_trend(
    trend_id: int, session: Session = Depends(get_session)
) -> TrendDetailOut:
    trend = session.get(Trend, trend_id)
    if not trend:
        raise HTTPException(status_code=404, detail="Trend not found")
    base = _trend_to_out(session, trend)
    assessment = session.exec(
        select(TrendAssessment).where(TrendAssessment.trend_id == trend.id)
    ).first()
    timepoints = session.exec(
        select(TopicTimepoint)
        .where(TopicTimepoint.topic_id == trend.topic_id)
        .order_by(TopicTimepoint.period)
    ).all()
    return TrendDetailOut(
        **base.model_dump(),
        rationale=assessment.rationale if assessment else None,
        evidence=trend.evidence or [],
        timeseries=[TimepointOut(period=t.period, doc_count=t.doc_count) for t in timepoints],
    )


@router.post("/trends/{trend_id}/feedback", response_model=FeedbackOut)
def add_feedback(
    trend_id: int, body: FeedbackIn, session: Session = Depends(get_session)
) -> ExpertFeedback:
    trend = session.get(Trend, trend_id)
    if not trend:
        raise HTTPException(status_code=404, detail="Trend not found")
    if body.action not in ("confirm", "correct", "reject"):
        raise HTTPException(
            status_code=422, detail="action must be confirm|correct|reject"
        )
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


@router.post("/trends/{trend_id}/translate", response_model=TranslateOut)
def translate_trend(
    trend_id: int, body: TranslateIn, session: Session = Depends(get_session)
) -> TranslateOut:
    """Translate a trend's title/summary/rationale into ``language`` on demand (ADR-28)."""
    from app.config import get_settings
    from app.pipeline.translate import resolve_translator

    trend = session.get(Trend, trend_id)
    if not trend:
        raise HTTPException(status_code=404, detail="Trend not found")
    if body.language not in ("en", "de"):
        raise HTTPException(status_code=422, detail="language must be en|de")
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


@router.post("/reference-trends", response_model=ReferenceTrendOut, status_code=201)
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


@router.delete("/reference-trends/{ref_id}", status_code=204)
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
        rows = session.exec(select(Trend).where(Trend.run_id == run_id)).all()
        for trend in rows:
            topic = session.get(Topic, trend.topic_id)
            trends.append(
                TrendLike(
                    id=trend.id,
                    title=trend.title,
                    keywords=(topic.keywords or []) if topic else [],
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
