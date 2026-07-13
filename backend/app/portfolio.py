"""Portfolio review operations with append-only, idempotent decisions."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session, select

from app.models import CanonicalTrend, TrendDecision, TrendOccurrence

_ACTIONS = {"confirm", "correct", "reject", "restore", "link", "create", "merge"}
_EDITABLE_FIELDS = {
    "title",
    "summary",
    "maturity",
    "pestel",
    "category",
    "impact",
    "urgency",
    "uncertainty",
    "radar_stage",
}


def record_decision(
    session: Session,
    *,
    canonical_trend_id: str,
    action: str,
    reviewer: str,
    idempotency_key: str,
    occurrence_id: int | None = None,
    values: dict | None = None,
    reason: str | None = None,
) -> TrendDecision:
    """Apply a review decision while deriving before-values on the server."""
    if action not in _ACTIONS:
        raise ValueError(f"Unsupported decision action: {action}")
    existing = session.exec(
        select(TrendDecision).where(
            TrendDecision.idempotency_key == idempotency_key
        )
    ).first()
    if existing:
        return existing
    canonical = session.get(CanonicalTrend, canonical_trend_id)
    if canonical is None:
        raise ValueError("Canonical trend does not exist")
    occurrence = session.get(TrendOccurrence, occurrence_id) if occurrence_id else None
    if occurrence and occurrence.canonical_trend_id != canonical.id:
        raise ValueError("Occurrence does not belong to canonical trend")

    updates = {key: value for key, value in (values or {}).items() if key in _EDITABLE_FIELDS}
    before = {key: getattr(canonical, key) for key in updates}
    before["status"] = canonical.status

    if action == "reject" and occurrence_id is None:
        canonical.status = "rejected"
    elif action == "restore":
        canonical.status = "active"
    elif action == "merge":
        target_id = (values or {}).get("merged_into_id")
        if not target_id or session.get(CanonicalTrend, target_id) is None:
            raise ValueError("Merge target does not exist")
        canonical.status = "merged"
        canonical.merged_into_id = target_id
    elif action in {"confirm", "correct", "link", "create"}:
        canonical.status = "active"

    for field, value in updates.items():
        setattr(canonical, field, value)
    canonical.updated_at = datetime.now(UTC)
    after = {key: getattr(canonical, key) for key in updates}
    after["status"] = canonical.status
    if canonical.merged_into_id:
        after["merged_into_id"] = canonical.merged_into_id

    decision = TrendDecision(
        canonical_trend_id=canonical.id,
        occurrence_id=occurrence_id,
        action=action,
        reviewer=reviewer,
        reason=reason,
        before_values=before,
        after_values=after,
        idempotency_key=idempotency_key,
    )
    session.add(canonical)
    session.add(decision)
    session.commit()
    session.refresh(decision)
    return decision
