"""Persistence tests for the core data model (including the pgvector column)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import select

from app.models import Chunk, Document, Source
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
