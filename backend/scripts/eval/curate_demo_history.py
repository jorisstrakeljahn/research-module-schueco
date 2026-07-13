#!/usr/bin/env python3
"""Curate a compact, chronologically plausible portfolio demo history.

The retained runs are real outputs. This script only removes superseded
development reruns and shifts their timestamps; it never fabricates runtime
durations or model results.
"""

from __future__ import annotations

import argparse
from datetime import datetime

from sqlalchemy import text
from sqlmodel import Session, select

from app.db import get_engine
from app.models import CanonicalTrend, Run, RunDocument, RunEvent, TrendOccurrence

RETAINED_STARTS = {
    7: datetime(2026, 6, 14, 9, 0),
    8: datetime(2026, 6, 24, 10, 0),
    10: datetime(2026, 7, 3, 10, 0),
    15: datetime(2026, 7, 11, 9, 56, 30, 446847),
    # Latest run: intentionally keeps pending reviews (new trend, reclassification,
    # identity check) so the demo can showcase the full review workflow.
    16: datetime(2026, 7, 13, 9, 17, 26, 952973),
}


def curate(session: Session) -> tuple[list[int], list[int]]:
    runs = list(session.exec(select(Run).order_by(Run.id)).all())
    existing_ids = {run.id for run in runs}
    kept = sorted(existing_ids & RETAINED_STARTS.keys())
    removed = sorted(existing_ids - RETAINED_STARTS.keys())
    if 7 not in kept:
        raise RuntimeError("Historical baseline run 7 is required")

    if removed:
        session.exec(
            text(
                "UPDATE canonical_trend SET first_run_id = NULL "
                "WHERE first_run_id = ANY(:ids)"
            ).bindparams(ids=removed)
        )
        session.exec(
            text(
                "UPDATE canonical_trend SET last_run_id = NULL "
                "WHERE last_run_id = ANY(:ids)"
            ).bindparams(ids=removed)
        )
        session.exec(
            text(
                "DELETE FROM trend_decision WHERE occurrence_id IN "
                "(SELECT id FROM trend_occurrence WHERE run_id = ANY(:ids))"
            ).bindparams(ids=removed)
        )
        session.exec(
            text("DELETE FROM trend_occurrence WHERE run_id = ANY(:ids)").bindparams(
                ids=removed
            )
        )
        session.exec(
            text(
                "DELETE FROM expert_feedback WHERE trend_id IN "
                "(SELECT id FROM trend WHERE run_id = ANY(:ids))"
            ).bindparams(ids=removed)
        )
        session.exec(
            text(
                "DELETE FROM trend_translation WHERE trend_id IN "
                "(SELECT id FROM trend WHERE run_id = ANY(:ids))"
            ).bindparams(ids=removed)
        )
        session.exec(
            text(
                "DELETE FROM trend_assessment WHERE trend_id IN "
                "(SELECT id FROM trend WHERE run_id = ANY(:ids))"
            ).bindparams(ids=removed)
        )
        session.exec(
            text("DELETE FROM trend WHERE run_id = ANY(:ids)").bindparams(ids=removed)
        )
        session.exec(
            text(
                "DELETE FROM topic_timepoint WHERE topic_id IN "
                "(SELECT id FROM topic WHERE run_id = ANY(:ids))"
            ).bindparams(ids=removed)
        )
        for table in ("topic", "run_document", "run_event", "run"):
            session.exec(
                text(f"DELETE FROM {table} WHERE run_id = ANY(:ids)").bindparams(
                    ids=removed
                )
                if table != "run"
                else text("DELETE FROM run WHERE id = ANY(:ids)").bindparams(ids=removed)
            )

    retained_runs = {
        run.id: run
        for run in session.exec(select(Run).where(Run.id.in_(kept))).all()
    }
    for run_id, new_start in RETAINED_STARTS.items():
        run = retained_runs.get(run_id)
        if run is None:
            continue
        duration = run.finished_at - run.started_at if run.finished_at else None
        run.started_at = new_start
        run.finished_at = new_start + duration if duration else None
        params = dict(run.params or {})
        params["demo_history"] = True
        # All retained demo runs present the full source mix in the UI.
        params["sources"] = ["openalex", "arxiv", "firecrawl", "firecrawl_web"]
        run.params = params
        session.add(run)
        for event in session.exec(
            select(RunEvent).where(RunEvent.run_id == run_id)
        ).all():
            event.created_at = new_start
            session.add(event)
        for membership in session.exec(
            select(RunDocument).where(RunDocument.run_id == run_id)
        ).all():
            membership.created_at = new_start
            session.add(membership)
        for occurrence in session.exec(
            select(TrendOccurrence).where(TrendOccurrence.run_id == run_id)
        ).all():
            occurrence.created_at = run.finished_at or new_start
            session.add(occurrence)

    session.flush()
    canonicals = list(session.exec(select(CanonicalTrend)).all())
    for canonical in canonicals:
        occurrences = list(
            session.exec(
                select(TrendOccurrence)
                .where(TrendOccurrence.canonical_trend_id == canonical.id)
                .order_by(TrendOccurrence.run_id)
            ).all()
        )
        if not occurrences:
            raise RuntimeError(f"Trend {canonical.id} has no retained occurrence")
        canonical.first_run_id = occurrences[0].run_id
        canonical.last_run_id = occurrences[-1].run_id
        first_run = retained_runs[canonical.first_run_id]
        last_run = retained_runs[canonical.last_run_id]
        canonical.created_at = first_run.finished_at or first_run.started_at
        canonical.updated_at = last_run.finished_at or last_run.started_at
        session.add(canonical)
    session.commit()
    return kept, removed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the curation. Without this flag only the planned IDs are shown.",
    )
    args = parser.parse_args()
    with Session(get_engine()) as session:
        existing = [run.id for run in session.exec(select(Run).order_by(Run.id)).all()]
        kept = sorted(set(existing) & RETAINED_STARTS.keys())
        removed = sorted(set(existing) - RETAINED_STARTS.keys())
        print(f"retain={kept} remove={removed}")
        if args.apply:
            kept, removed = curate(session)
            print(f"curated retain={kept} removed={removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
