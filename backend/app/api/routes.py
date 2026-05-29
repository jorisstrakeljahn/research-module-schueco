"""API routes for runs, trends and expert feedback."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.db import get_session
from app.models import (
    ExpertFeedback,
    Run,
    Topic,
    TopicTimepoint,
    Trend,
    TrendAssessment,
)
from app.schemas import (
    FeedbackIn,
    FeedbackOut,
    RunOut,
    TimepointOut,
    TrendDetailOut,
    TrendOut,
)

router = APIRouter()


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
        keywords=topic.keywords or [],
        size=topic.size,
        pestel=assessment.pestel if assessment else None,
        impact=assessment.impact if assessment else None,
        uncertainty=assessment.uncertainty if assessment else None,
        radar_stage=assessment.radar_stage if assessment else None,
    )


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/runs", response_model=list[RunOut])
def list_runs(session: Session = Depends(get_session)) -> list[Run]:
    return session.exec(select(Run).order_by(Run.id.desc())).all()


@router.get("/trends", response_model=list[TrendOut])
def list_trends(
    run_id: int | None = Query(default=None, description="Defaults to latest run"),
    maturity: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[TrendOut]:
    if run_id is None:
        run_id = _latest_completed_run_id(session)
    if run_id is None:
        return []
    query = select(Trend).where(Trend.run_id == run_id)
    if maturity:
        query = query.where(Trend.maturity == maturity)
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
    timepoints = session.exec(
        select(TopicTimepoint)
        .where(TopicTimepoint.topic_id == trend.topic_id)
        .order_by(TopicTimepoint.period)
    ).all()
    return TrendDetailOut(
        **base.model_dump(),
        evidence=trend.evidence or [],
        timeseries=[TimepointOut(period=t.period, doc_count=t.doc_count) for t in timepoints],
    )


@router.post("/trends/{trend_id}/feedback", response_model=FeedbackOut)
def add_feedback(
    trend_id: int, body: FeedbackIn, session: Session = Depends(get_session)
) -> ExpertFeedback:
    if not session.get(Trend, trend_id):
        raise HTTPException(status_code=404, detail="Trend not found")
    if body.action not in ("confirm", "correct", "reject"):
        raise HTTPException(
            status_code=422, detail="action must be confirm|correct|reject"
        )
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
