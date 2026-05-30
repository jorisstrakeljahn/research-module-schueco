"""End-to-end pipeline test using a fake connector and the offline components."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import select

from app.ingestion.base import RawDocument
from app.models import Chunk, Topic, TopicTimepoint, Trend
from app.pipeline.run import run_pipeline
from tests.conftest import requires_db


class FakeConnector:
    source_name = "TestSource"
    source_type = "science"

    def __init__(self, docs: list[RawDocument]) -> None:
        self._docs = docs

    def fetch(self, query: str, limit: int = 50) -> list[RawDocument]:
        return self._docs[:limit]


def _make_docs() -> list[RawDocument]:
    insulation = [
        "thermal insulation envelope retrofit efficiency standards",
        "insulated envelope retrofit reduces heating demand",
        "envelope insulation thermal retrofit performance metrics",
        "retrofit insulation thermal envelope efficiency buildings",
    ]
    twin = [
        "digital twin simulation modeling workflow construction",
        "simulation digital twin data modeling pipeline",
        "modeling workflow digital twin simulation platform",
        "digital twin construction simulation modeling analytics",
    ]
    docs: list[RawDocument] = []
    for i, text in enumerate(insulation + twin):
        year = 2022 + (i % 3)
        docs.append(
            RawDocument(
                external_id=f"ext-{i}",
                title=text[:30],
                text=text,
                url=f"http://example.org/{i}",
                published_at=datetime(year, 1 + (i % 4) * 3, 1, tzinfo=UTC),
                language="en",
                source_name="TestSource",
                source_type="science",
            )
        )
    return docs


@requires_db
def test_run_pipeline_end_to_end(session):
    connector = FakeConnector(_make_docs())
    run = run_pipeline("buildings", session=session, limit=50, connector=connector)

    assert run.status == "completed"
    assert run.n_documents == 8
    assert run.n_topics >= 1

    topics = session.exec(select(Topic).where(Topic.run_id == run.id)).all()
    assert len(topics) == run.n_topics
    assert all(t.keywords for t in topics)

    trends = session.exec(select(Trend).where(Trend.run_id == run.id)).all()
    assert len(trends) == run.n_topics
    assert all(t.title and t.summary for t in trends)
    assert all(t.maturity for t in trends)

    # chunks have embeddings of the configured dimension
    chunks = session.exec(select(Chunk)).all()
    assert len(chunks) == 8
    assert all(c.embedding is not None and len(c.embedding) == 384 for c in chunks)

    # at least one topic has a time series
    timepoints = session.exec(select(TopicTimepoint)).all()
    assert len(timepoints) >= 1
