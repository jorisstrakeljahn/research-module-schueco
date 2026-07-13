"""Deterministic one-to-one matching of run topics to canonical trends."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from scipy.optimize import linear_sum_assignment
from sqlmodel import Session, select

from app.models import (
    CanonicalTrend,
    RunDocument,
    Topic,
    TopicTimepoint,
    Trend,
    TrendAssessment,
    TrendOccurrence,
)
from app.pipeline.translate import translations_for_trend


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
        select(CanonicalTrend).where(
            CanonicalTrend.status != "merged",
            CanonicalTrend.status != "review",
        )
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


_ALWAYS_MATERIAL_FIELDS = ("title", "maturity")
_ALWAYS_MATERIAL_ASSESSMENT_FIELDS = ("pestel", "category", "radar_stage")
_SCORED_ASSESSMENT_FIELDS = ("impact", "urgency", "uncertainty")

# Recomputed scores drift by tiny floating-point amounts between runs;
# differences below this tolerance are treated as identical values.
_NUMERIC_NOISE_TOLERANCE = 0.05


def values_differ(left: object, right: object) -> bool:
    if isinstance(left, list) and isinstance(right, list):
        return sorted(left) != sorted(right)
    if (
        isinstance(left, (int, float))
        and isinstance(right, (int, float))
        and not isinstance(left, bool)
        and not isinstance(right, bool)
    ):
        return abs(float(left) - float(right)) > _NUMERIC_NOISE_TOLERANCE
    return left != right


def _score_delta_is_material(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return left != right
    return abs(float(left) - float(right)) >= 2


def sanitize_change(
    change_type: str,
    changed_fields: Sequence[str],
    before: Mapping[str, object] | None,
    after: Mapping[str, object],
    *,
    evidence_changed: bool,
) -> tuple[str, list[str]]:
    """Drop no-op field diffs (e.g. float noise in stored data) and re-derive the change type."""
    if change_type not in {"classification_changed", "content_changed"} or before is None:
        return change_type, list(changed_fields)
    kept = [
        field
        for field in changed_fields
        if values_differ(before.get(field), after.get(field))
    ]
    material = [
        field
        for field in kept
        if field in _ALWAYS_MATERIAL_FIELDS
        or field in _ALWAYS_MATERIAL_ASSESSMENT_FIELDS
        or (
            field in _SCORED_ASSESSMENT_FIELDS
            and _score_delta_is_material(
                _as_score(before.get(field)), _as_score(after.get(field))
            )
        )
    ]
    if material:
        return "classification_changed", kept
    if kept:
        return "content_changed", kept
    return ("evidence_only" if evidence_changed else "unchanged"), []


def _as_score(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _prevalence_for_topic(session: Session, topic_id: int) -> float | None:
    point = session.exec(
        select(TopicTimepoint)
        .where(TopicTimepoint.topic_id == topic_id)
        .order_by(TopicTimepoint.period.desc(), TopicTimepoint.id.desc())
    ).first()
    return point.prevalence if point else None


def _previous_occurrence(
    session: Session, canonical_id: str, run_id: int
) -> TrendOccurrence | None:
    return session.exec(
        select(TrendOccurrence)
        .where(
            TrendOccurrence.canonical_trend_id == canonical_id,
            TrendOccurrence.run_id < run_id,
        )
        .order_by(TrendOccurrence.run_id.desc(), TrendOccurrence.id.desc())
    ).first()


def _review_reason(
    code: str,
    *,
    kind: str,
    field: str | None = None,
    before: object = None,
    after: object = None,
) -> dict:
    reason = {"code": code, "kind": kind}
    if field is not None:
        reason.update({"field": field, "before": before, "after": after})
    return reason


def proposed_values(
    trend: Trend, assessment: TrendAssessment | None
) -> dict[str, object]:
    values: dict[str, object] = {
        "title": trend.title,
        "summary": trend.summary,
        "maturity": trend.maturity,
    }
    if assessment:
        values.update(
            {
                field: getattr(assessment, field)
                for field in (
                    "pestel",
                    "category",
                    "impact",
                    "urgency",
                    "uncertainty",
                    "radar_stage",
                )
            }
        )
    return values


def reconcile_run(
    session: Session,
    *,
    run_id: int,
    threshold: float,
    review_threshold: float,
    margin_threshold: float,
    max_new_trends: int | None = None,
) -> list[TrendOccurrence]:
    """Create occurrences and apply only changes that do not require review.

    ``max_new_trends`` caps how many brand-new (unmatched) trends enter the
    portfolio/review pipeline per run; the largest topics win. Surplus new
    trends stay visible in the run itself but get no occurrence, so the review
    queue and the pending markers in the UI stay digestible.
    """
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
    allowed_new_ids: set[int] | None = None
    if max_new_trends is not None:
        unmatched = [trend for trend in trends if str(trend.id) not in matches]
        ranked = sorted(
            unmatched,
            key=lambda item: topics[item.topic_id].size,
            reverse=True,
        )
        allowed_new_ids = {item.id for item in ranked[:max_new_trends]}
    occurrences: list[TrendOccurrence] = []
    for trend in trends:
        assessment = session.exec(
            select(TrendAssessment).where(TrendAssessment.trend_id == trend.id)
        ).first()
        match = matches.get(str(trend.id))
        canonical = session.get(CanonicalTrend, match.canonical_key) if match else None
        if (
            canonical is None
            and allowed_new_ids is not None
            and trend.id not in allowed_new_ids
        ):
            continue
        current_documents = _documents_for_topic(
            session, run_id, topics[trend.topic_id].topic_index
        )
        review_reasons: list[dict] = []
        if canonical is None:
            change_type = "new"
            changed_fields = list(proposed_values(trend, assessment))
            review_reasons.append(_review_reason("new_trend", kind="classification"))
            previous_documents: frozenset[int] = frozenset()
        else:
            proposed = proposed_values(trend, assessment)
            changed_fields = [
                field
                for field, value in proposed.items()
                if values_differ(getattr(canonical, field), value)
            ]
            material_fields = [
                field
                for field in _ALWAYS_MATERIAL_FIELDS
                if field in changed_fields
            ]
            material_fields.extend(
                field
                for field in _ALWAYS_MATERIAL_ASSESSMENT_FIELDS
                if field in changed_fields
            )
            material_fields.extend(
                field
                for field in _SCORED_ASSESSMENT_FIELDS
                if field in changed_fields
                and _score_delta_is_material(
                    getattr(canonical, field), proposed[field]
                )
            )
            if match.review_reason:
                review_reasons.append(
                    _review_reason(match.review_reason, kind="identity")
                )
            # Every genuine content change needs a human decision; only
            # evidence-only updates are applied automatically.
            review_reasons.extend(
                _review_reason(
                    "material_change" if field in material_fields else "content_change",
                    kind="classification",
                    field=field,
                    before=getattr(canonical, field),
                    after=proposed[field],
                )
                for field in changed_fields
            )
            previous = _previous_occurrence(session, canonical.id, run_id)
            if previous:
                previous_trend = session.get(Trend, previous.trend_id)
                previous_topic = (
                    session.get(Topic, previous_trend.topic_id) if previous_trend else None
                )
                previous_documents = (
                    _documents_for_topic(
                        session,
                        previous.run_id,
                        previous_topic.topic_index,
                    )
                    if previous_topic
                    else frozenset()
                )
            else:
                previous_documents = frozenset()
            if material_fields:
                change_type = "classification_changed"
            elif changed_fields:
                change_type = "content_changed"
            elif current_documents != previous_documents:
                change_type = "evidence_only"
            else:
                change_type = "unchanged"
            if not review_reasons:
                for field, value in proposed.items():
                    setattr(canonical, field, value)
                canonical.translations = translations_for_trend(
                    session,
                    trend.id,
                    fallback_title=trend.title,
                    fallback_summary=trend.summary,
                    fallback_rationale=assessment.rationale if assessment else None,
                )
                canonical.last_run_id = run_id
                canonical.updated_at = trend.created_at
        evidence_added_count = len(current_documents - previous_documents)
        evidence_removed_count = len(previous_documents - current_documents)
        occurrence = TrendOccurrence(
            canonical_trend_id=canonical.id if canonical else None,
            trend_id=trend.id,
            run_id=run_id,
            change_type=change_type,
            match_score=match.score if match else None,
            match_margin=match.margin if match else None,
            changed_fields=changed_fields,
            review_status="pending" if review_reasons else "not_required",
            review_reasons=review_reasons or None,
            evidence_added_count=evidence_added_count,
            evidence_removed_count=evidence_removed_count,
            review_reason=review_reasons[0]["code"] if review_reasons else None,
            prevalence=_prevalence_for_topic(session, trend.topic_id),
        )
        if canonical:
            session.add(canonical)
        session.add(occurrence)
        occurrences.append(occurrence)
    session.flush()
    return occurrences
