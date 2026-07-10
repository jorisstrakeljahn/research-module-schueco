"""Feedback-driven learning (human-in-the-loop, ADR-02).

Expert feedback closes the loop: confirmed/corrected trends feed their vocabulary back
into the next crawl as additional seed terms, while rejected trends contribute negative
terms used by the relevance gate. Over successive runs this steers the system toward
what experts consider relevant - the mechanism by which it "gets smarter over time".
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models import CanonicalTrend, ExpertFeedback, Topic, Trend, TrendOccurrence


def _keywords_for_trend(session: Session, trend: Trend, top_n: int = 3) -> list[str]:
    topic = session.get(Topic, trend.topic_id)
    if topic and topic.keywords:
        return list(topic.keywords[:top_n])
    return []


def seeds_from_feedback(session: Session, limit: int = 20) -> list[str]:
    """Derive new seed terms from confirmed or corrected trends."""
    feedbacks = session.exec(
        select(ExpertFeedback).where(ExpertFeedback.action.in_(("confirm", "correct")))
    ).all()

    terms: list[str] = []
    seen: set[str] = set()

    def _add(term: str | None) -> None:
        if not term:
            return
        term = term.strip()
        low = term.lower()
        if term and low not in seen:
            seen.add(low)
            terms.append(term)

    for fb in feedbacks:
        trend = session.get(Trend, fb.trend_id)
        if not trend:
            continue
        # A corrected title is a strong, expert-provided signal.
        if fb.action == "correct" and fb.field == "title":
            _add(fb.new_value)
        else:
            _add(trend.title)
        for kw in _keywords_for_trend(session, trend):
            _add(kw)

    return terms[:limit]


def seeds_from_portfolio(session: Session, limit: int = 12) -> list[str]:
    """Use accepted portfolio identities as context for the next focused crawl."""
    canonicals = session.exec(
        select(CanonicalTrend)
        .where(CanonicalTrend.status == "active")
        .order_by(CanonicalTrend.updated_at.desc())
        .limit(limit)
    ).all()
    return [trend.title.strip() for trend in canonicals if trend.title.strip()]


def negative_terms_from_feedback(session: Session, limit: int = 20) -> list[str]:
    """Derive negative (exclusion) terms from rejected trends."""
    feedbacks = session.exec(
        select(ExpertFeedback).where(ExpertFeedback.action == "reject")
    ).all()

    terms: list[str] = []
    seen: set[str] = set()
    for fb in feedbacks:
        trend = session.get(Trend, fb.trend_id)
        if not trend:
            continue
        for kw in _keywords_for_trend(session, trend, top_n=5):
            low = kw.lower()
            if low not in seen:
                seen.add(low)
                terms.append(kw)

    rejected = session.exec(
        select(CanonicalTrend).where(CanonicalTrend.status == "rejected")
    ).all()
    for canonical in rejected:
        occurrence = session.exec(
            select(TrendOccurrence)
            .where(TrendOccurrence.canonical_trend_id == canonical.id)
            .order_by(TrendOccurrence.run_id.desc())
        ).first()
        trend = session.get(Trend, occurrence.trend_id) if occurrence else None
        if trend is None:
            continue
        for keyword in _keywords_for_trend(session, trend, top_n=5):
            low = keyword.lower()
            if low not in seen:
                seen.add(low)
                terms.append(keyword)

    return terms[:limit]
