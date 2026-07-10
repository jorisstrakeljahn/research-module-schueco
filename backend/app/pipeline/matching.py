"""Deterministic one-to-one matching of run topics to canonical trends."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import numpy as np
from scipy.optimize import linear_sum_assignment
from sqlmodel import Session, select

from app.models import (
    CanonicalTrend,
    RunDocument,
    Topic,
    Trend,
    TrendAssessment,
    TrendOccurrence,
)


@dataclass(frozen=True)
class MatchCandidate:
    key: str
    centroid: np.ndarray | None
    keywords: frozenset[str]
    document_ids: frozenset[int]
    status: str = "active"


@dataclass(frozen=True)
class Match:
    current_key: str
    canonical_key: str
    score: float
    margin: float
    review_reason: str | None = None


def _cosine(left: np.ndarray | None, right: np.ndarray | None) -> float:
    if left is None or right is None or not left.size or not right.size:
        return 0.0
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(np.dot(left, right) / denominator) if denominator else 0.0


def _jaccard(left: frozenset, right: frozenset) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def similarity(current: MatchCandidate, canonical: MatchCandidate) -> float:
    return (
        0.65 * max(0.0, _cosine(current.centroid, canonical.centroid))
        + 0.20 * _jaccard(current.document_ids, canonical.document_ids)
        + 0.15 * _jaccard(current.keywords, canonical.keywords)
    )


def one_to_one_match(
    current: list[MatchCandidate],
    canonical: list[MatchCandidate],
    *,
    threshold: float = 0.62,
    review_threshold: float = 0.50,
    margin_threshold: float = 0.08,
) -> list[Match]:
    if not current or not canonical:
        return []
    scores = np.asarray(
        [[similarity(item, known) for known in canonical] for item in current]
    )
    rows, columns = linear_sum_assignment(-scores)
    matches: list[Match] = []
    assigned_rows = set(int(row) for row in rows)
    for row, column in zip(rows, columns, strict=True):
        score = float(scores[row, column])
        alternatives = np.delete(scores[row], column)
        margin = score - float(alternatives.max()) if alternatives.size else score
        if score < review_threshold:
            continue
        reason = None
        if canonical[column].status == "rejected":
            reason = "matched_rejected"
        elif score < threshold:
            reason = "below_match_threshold"
        elif margin < margin_threshold:
            reason = "ambiguous_margin"
        matches.append(
            Match(
                current_key=current[row].key,
                canonical_key=canonical[column].key,
                score=score,
                margin=margin,
                review_reason=reason,
            )
        )
    for row in sorted(set(range(len(current))) - assigned_rows):
        column = int(np.argmax(scores[row]))
        score = float(scores[row, column])
        if score >= review_threshold:
            matches.append(
                Match(
                    current_key=current[row].key,
                    canonical_key=canonical[column].key,
                    score=score,
                    margin=0.0,
                    review_reason="split_candidate",
                )
            )
    return matches


def _documents_for_topic(session: Session, run_id: int, topic_index: int) -> frozenset[int]:
    rows = session.exec(
        select(RunDocument.document_id).where(
            RunDocument.run_id == run_id,
            RunDocument.topic_index == topic_index,
            RunDocument.is_outlier.is_(False),
        )
    ).all()
    return frozenset(rows)


def _canonical_candidates(session: Session) -> list[MatchCandidate]:
    candidates: list[MatchCandidate] = []
    canonicals = session.exec(
        select(CanonicalTrend).where(CanonicalTrend.status != "merged")
    ).all()
    for canonical in canonicals:
        occurrence = session.exec(
            select(TrendOccurrence)
            .where(TrendOccurrence.canonical_trend_id == canonical.id)
            .order_by(TrendOccurrence.run_id.desc())
        ).first()
        if not occurrence:
            continue
        trend = session.get(Trend, occurrence.trend_id)
        topic = session.get(Topic, trend.topic_id) if trend else None
        if not trend or not topic:
            continue
        candidates.append(
            MatchCandidate(
                key=canonical.id,
                centroid=np.asarray(topic.centroid) if topic.centroid is not None else None,
                keywords=frozenset(word.casefold() for word in (topic.keywords or [])),
                document_ids=_documents_for_topic(
                    session, occurrence.run_id, topic.topic_index
                ),
                status=canonical.status,
            )
        )
    return candidates


def reconcile_run(
    session: Session,
    *,
    run_id: int,
    threshold: float,
    review_threshold: float,
    margin_threshold: float,
) -> list[TrendOccurrence]:
    """Create occurrences and update portfolio values in the caller's transaction."""
    trends = list(session.exec(select(Trend).where(Trend.run_id == run_id)).all())
    topics = {topic.id: topic for topic in session.exec(
        select(Topic).where(Topic.run_id == run_id)
    ).all()}
    current = [
        MatchCandidate(
            key=str(trend.id),
            centroid=np.asarray(topics[trend.topic_id].centroid)
            if topics[trend.topic_id].centroid is not None
            else None,
            keywords=frozenset(
                word.casefold() for word in (topics[trend.topic_id].keywords or [])
            ),
            document_ids=_documents_for_topic(
                session, run_id, topics[trend.topic_id].topic_index
            ),
        )
        for trend in trends
    ]
    known = _canonical_candidates(session)
    matches = {
        match.current_key: match
        for match in one_to_one_match(
            current,
            known,
            threshold=threshold,
            review_threshold=review_threshold,
            margin_threshold=margin_threshold,
        )
    }
    occurrences: list[TrendOccurrence] = []
    for trend in trends:
        assessment = session.exec(
            select(TrendAssessment).where(TrendAssessment.trend_id == trend.id)
        ).first()
        match = matches.get(str(trend.id))
        canonical = session.get(CanonicalTrend, match.canonical_key) if match else None
        if canonical is None:
            canonical = CanonicalTrend(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"run:{run_id}:trend:{trend.id}")),
                status="active",
                title=trend.title,
                summary=trend.summary,
                maturity=trend.maturity,
                first_run_id=run_id,
                last_run_id=run_id,
            )
            change_type = "new"
            changed_fields = ["title", "summary", "maturity"]
            session.add(canonical)
            session.flush()
        else:
            changed_fields = [
                field
                for field in ("title", "summary", "maturity")
                if getattr(canonical, field) != getattr(trend, field)
            ]
            if assessment:
                changed_fields.extend(
                    field
                    for field in (
                        "pestel",
                        "category",
                        "impact",
                        "urgency",
                        "uncertainty",
                        "radar_stage",
                    )
                    if getattr(canonical, field) != getattr(assessment, field)
                )
            change_type = (
                "review"
                if match.review_reason
                else ("updated" if changed_fields else "unchanged")
            )
            if not match.review_reason:
                canonical.title = trend.title
                canonical.summary = trend.summary
                canonical.maturity = trend.maturity
                canonical.last_run_id = run_id
        if assessment and (not match or not match.review_reason):
            for field in (
                "pestel",
                "category",
                "impact",
                "urgency",
                "uncertainty",
                "radar_stage",
            ):
                setattr(canonical, field, getattr(assessment, field))
        occurrence = TrendOccurrence(
            canonical_trend_id=canonical.id,
            trend_id=trend.id,
            run_id=run_id,
            change_type=change_type,
            match_score=match.score if match else None,
            match_margin=match.margin if match else None,
            changed_fields=changed_fields,
            review_reason=match.review_reason if match else None,
        )
        session.add(canonical)
        session.add(occurrence)
        occurrences.append(occurrence)
    session.flush()
    return occurrences
