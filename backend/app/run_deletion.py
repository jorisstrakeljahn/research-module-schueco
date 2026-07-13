"""Full rollback of a pipeline run (demo/testing helper).

Deleting a run removes everything the run added and restores the portfolio to
its previous state:

* review decisions made on this run's occurrences are reverted via their
  stored ``before_values`` (append-only trail is truncated for this run),
* canonical trends first seen in this run are removed,
* canonical trends whose latest observation was this run fall back to their
  previous occurrence,
* run-scoped rows (trends, topics, occurrences, events, translations, …) and
  documents ingested exclusively for this run are deleted.

Only the most recent run can be rolled back (older runs are load-bearing for
later occurrences); runs without any topics/occurrences (e.g. failed runs)
can always be deleted.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import text
from sqlmodel import Session, col, delete, select

from app.models import (
    BaselineSnapshot,
    CanonicalTrend,
    Chunk,
    Document,
    DocumentEmbedding,
    ExpertFeedback,
    Run,
    RunDocument,
    RunEvent,
    Topic,
    TopicTimepoint,
    Trend,
    TrendAssessment,
    TrendDecision,
    TrendOccurrence,
    TrendTranslation,
)

_REVERTIBLE_FIELDS = (
    "title",
    "summary",
    "maturity",
    "pestel",
    "category",
    "impact",
    "urgency",
    "uncertainty",
    "radar_stage",
    "status",
)


class RunDeletionError(Exception):
    """Deletion is not allowed in the current state."""


def _ensure_deletable(session: Session, run: Run) -> None:
    if run.status == "running":
        raise RunDeletionError("A running run cannot be deleted")
    baseline = session.exec(
        select(BaselineSnapshot).where(BaselineSnapshot.source_run_id == run.id)
    ).first()
    if baseline is not None:
        raise RunDeletionError(
            "This run is the source of an evaluation baseline and cannot be deleted"
        )
    has_content = (
        session.exec(select(Topic.id).where(Topic.run_id == run.id)).first()
        is not None
        or session.exec(
            select(TrendOccurrence.id).where(TrendOccurrence.run_id == run.id)
        ).first()
        is not None
    )
    if not has_content:
        return
    # Later runs diff against this run's state; rolling back a run in the
    # middle of the history would corrupt the portfolio audit trail.
    newer_with_content = session.exec(
        select(TrendOccurrence.id)
        .join(Run, Run.id == TrendOccurrence.run_id)
        .where(Run.id > run.id)
        .limit(1)
    ).first()
    if newer_with_content is not None:
        raise RunDeletionError(
            "Only the most recent run can be deleted; delete newer runs first"
        )


def _revert_decisions(session: Session, occurrence_ids: list[int]) -> int:
    """Undo review decisions made on this run's occurrences (newest first)."""
    if not occurrence_ids:
        return 0
    decisions = session.exec(
        select(TrendDecision)
        .where(col(TrendDecision.occurrence_id).in_(occurrence_ids))
        .order_by(TrendDecision.id.desc())
    ).all()
    for decision in decisions:
        canonical = (
            session.get(CanonicalTrend, decision.canonical_trend_id)
            if decision.canonical_trend_id
            else None
        )
        if canonical is not None and decision.before_values:
            for field in _REVERTIBLE_FIELDS:
                if field in decision.before_values:
                    setattr(canonical, field, decision.before_values[field])
            if decision.action == "merge":
                canonical.merged_into_id = None
            session.add(canonical)
        session.delete(decision)
    session.flush()
    return len(decisions)


def _delete_created_canonicals(session: Session, run_id: int) -> int:
    """Remove portfolio identities whose first observation was this run."""
    created = session.exec(
        select(CanonicalTrend).where(CanonicalTrend.first_run_id == run_id)
    ).all()
    if not created:
        return 0
    ids = [canonical.id for canonical in created]
    # Clear dangling references before removing the identities themselves.
    for other in session.exec(
        select(CanonicalTrend).where(col(CanonicalTrend.merged_into_id).in_(ids))
    ).all():
        other.merged_into_id = None
        session.add(other)
    session.exec(
        delete(TrendDecision).where(col(TrendDecision.canonical_trend_id).in_(ids))
    )
    for occurrence in session.exec(
        select(TrendOccurrence).where(
            col(TrendOccurrence.canonical_trend_id).in_(ids)
        )
    ).all():
        occurrence.canonical_trend_id = None
        session.add(occurrence)
    session.flush()
    for canonical in created:
        session.delete(canonical)
    session.flush()
    return len(created)


def _restore_touched_canonicals(session: Session, run_id: int) -> int:
    """Point canonicals whose latest observation was this run back to the
    previous run's occurrence."""
    touched = session.exec(
        select(CanonicalTrend).where(CanonicalTrend.last_run_id == run_id)
    ).all()
    restored = 0
    for canonical in touched:
        previous = session.exec(
            select(TrendOccurrence)
            .where(
                TrendOccurrence.canonical_trend_id == canonical.id,
                TrendOccurrence.run_id < run_id,
            )
            .order_by(TrendOccurrence.run_id.desc(), TrendOccurrence.id.desc())
        ).first()
        canonical.last_run_id = previous.run_id if previous else canonical.first_run_id
        canonical.updated_at = datetime.now(UTC)
        session.add(canonical)
        restored += 1
    session.flush()
    return restored


def _delete_run_rows(session: Session, run_id: int) -> None:
    trend_ids = list(
        session.exec(select(Trend.id).where(Trend.run_id == run_id)).all()
    )
    topic_ids = list(
        session.exec(select(Topic.id).where(Topic.run_id == run_id)).all()
    )
    session.exec(
        delete(TrendOccurrence).where(TrendOccurrence.run_id == run_id)
    )
    if trend_ids:
        session.exec(
            delete(TrendTranslation).where(
                col(TrendTranslation.trend_id).in_(trend_ids)
            )
        )
        session.exec(
            delete(ExpertFeedback).where(col(ExpertFeedback.trend_id).in_(trend_ids))
        )
        session.exec(
            delete(TrendAssessment).where(
                col(TrendAssessment.trend_id).in_(trend_ids)
            )
        )
        session.exec(delete(Trend).where(col(Trend.id).in_(trend_ids)))
    if topic_ids:
        session.exec(
            delete(TopicTimepoint).where(col(TopicTimepoint.topic_id).in_(topic_ids))
        )
        session.exec(delete(Topic).where(col(Topic.id).in_(topic_ids)))
    session.exec(delete(RunEvent).where(RunEvent.run_id == run_id))
    session.flush()


def _delete_orphaned_documents(session: Session, run_id: int) -> int:
    """Remove documents ingested for this run that no other run references."""
    document_ids = set(
        session.exec(
            select(RunDocument.document_id).where(RunDocument.run_id == run_id)
        ).all()
    )
    session.exec(delete(RunDocument).where(RunDocument.run_id == run_id))
    session.flush()
    if not document_ids:
        return 0
    still_referenced = set(
        session.exec(
            select(RunDocument.document_id).where(
                col(RunDocument.document_id).in_(document_ids)
            )
        ).all()
    )
    orphaned = document_ids - still_referenced
    if not orphaned:
        return 0
    for doc in session.exec(
        select(Document).where(
            col(Document.duplicate_of_id).in_(orphaned)
            | col(Document.near_duplicate_of_id).in_(orphaned)
        )
    ).all():
        if doc.duplicate_of_id in orphaned:
            doc.duplicate_of_id = None
        if doc.near_duplicate_of_id in orphaned:
            doc.near_duplicate_of_id = None
        session.add(doc)
    session.flush()
    session.exec(delete(Chunk).where(col(Chunk.document_id).in_(orphaned)))
    session.exec(
        delete(DocumentEmbedding).where(
            col(DocumentEmbedding.document_id).in_(orphaned)
        )
    )
    session.exec(delete(Document).where(col(Document.id).in_(orphaned)))
    session.flush()
    return len(orphaned)


def delete_run(session: Session, run_id: int) -> dict:
    """Delete a run and roll back every change it introduced."""
    run = session.get(Run, run_id)
    if run is None:
        raise LookupError("Run not found")
    _ensure_deletable(session, run)

    occurrence_ids = list(
        session.exec(
            select(TrendOccurrence.id).where(TrendOccurrence.run_id == run_id)
        ).all()
    )
    # The decision trail is protected by an immutability trigger (append-only
    # by design). A full run rollback is the one sanctioned exception; the
    # trigger is suspended only inside this transaction.
    session.connection().execute(
        text("ALTER TABLE trend_decision DISABLE TRIGGER trend_decision_immutable")
    )
    try:
        reverted_decisions = _revert_decisions(session, occurrence_ids)
        removed_canonicals = _delete_created_canonicals(session, run_id)
        _delete_run_rows(session, run_id)
        restored_canonicals = _restore_touched_canonicals(session, run_id)
        removed_documents = _delete_orphaned_documents(session, run_id)
        session.delete(run)
        session.connection().execute(
            text("ALTER TABLE trend_decision ENABLE TRIGGER trend_decision_immutable")
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return {
        "deleted_run_id": run_id,
        "reverted_decisions": reverted_decisions,
        "removed_canonical_trends": removed_canonicals,
        "restored_canonical_trends": restored_canonicals,
        "removed_documents": removed_documents,
    }
