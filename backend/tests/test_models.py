"""Persistence tests for the core data model (including the pgvector column)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import DBAPIError
from sqlmodel import select

from app.baseline import BASELINE_KEY, BASELINE_ROWS, BASELINE_TREND_IDS
from app.models import (
    BaselineSnapshot,
    CanonicalTrend,
    Chunk,
    Document,
    Source,
    TrendDecision,
)
from app.portfolio import record_decision
from tests.conftest import requires_db


@requires_db
def test_source_document_chunk_roundtrip(session):
    source = Source(
        name="OpenAlex", source_type="science", region="global", language="en"
    )
    session.add(source)
    session.commit()
    session.refresh(source)

    doc = Document(
        source_id=source.id,
        title="Adaptive facade systems",
        text="A study on adaptive building envelopes.",
        published_at=datetime(2024, 3, 1, tzinfo=UTC),
        language="en",
        region="global",
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)

    chunk = Chunk(document_id=doc.id, text="adaptive facade", embedding=[0.1] * 384)
    session.add(chunk)
    session.commit()

    loaded = session.exec(select(Chunk).where(Chunk.document_id == doc.id)).one()
    assert loaded.embedding is not None
    assert len(loaded.embedding) == 384
    assert loaded.document.title == "Adaptive facade systems"
    assert loaded.document.source.name == "OpenAlex"


@requires_db
def test_region_filtering(session):
    session.add_all(
        [
            Source(name="A", source_type="news", region="china", country="CN"),
            Source(name="B", source_type="news", region="europe", country="DE"),
        ]
    )
    session.commit()

    china = session.exec(select(Source).where(Source.region == "china")).all()
    assert len(china) == 1
    assert china[0].country == "CN"


def test_accepted_baseline_mapping_is_exact_and_ordered():
    assert BASELINE_KEY == "schueco-table-3-2026"
    assert BASELINE_TREND_IDS == (34, 49, 33, 40, 38, 48, 36, 45, 41, 46, 47)
    assert len(set(BASELINE_TREND_IDS)) == 11
    assert BASELINE_ROWS[0] == (
        34,
        "Adaptive Reuse",
        4.0,
        "bekannt, nicht aktiv",
        5.0,
    )
    assert BASELINE_ROWS[9] == (
        46,
        "Construction Servitization",
        5.0,
        "bekannt, nicht aktiv",
        4.0,
    )
    assert sum(row[3] == "bekannt, aktiv" for row in BASELINE_ROWS) == 5


@requires_db
def test_baseline_snapshot_is_database_immutable(session):
    snapshot = BaselineSnapshot(key="immutable-test", title="Original", source="test")
    session.add(snapshot)
    session.commit()
    snapshot.title = "Changed"
    session.add(snapshot)
    with pytest.raises(DBAPIError, match="immutable"):
        session.commit()
    session.rollback()


@requires_db
def test_trend_decisions_are_idempotent_and_append_only(session):
    session.add(CanonicalTrend(id="canonical-1", title="Original"))
    session.commit()
    first = record_decision(
        session,
        canonical_trend_id="canonical-1",
        action="correct",
        reviewer="tester",
        idempotency_key="decision-1",
        values={"title": "Corrected"},
    )
    repeated = record_decision(
        session,
        canonical_trend_id="canonical-1",
        action="correct",
        reviewer="tester",
        idempotency_key="decision-1",
        values={"title": "Ignored"},
    )
    assert repeated.id == first.id
    assert first.before_values["title"] == "Original"
    assert session.get(CanonicalTrend, "canonical-1").title == "Corrected"
    assert len(session.exec(select(TrendDecision)).all()) == 1
    first.reason = "mutated"
    session.add(first)
    with pytest.raises(DBAPIError, match="immutable"):
        session.commit()
    session.rollback()
