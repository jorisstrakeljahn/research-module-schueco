"""End-to-end pipeline test using a fake connector and the offline components."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.db import get_engine
from app.ingestion.base import RawDocument
from app.models import (
    PESTEL_DIMENSIONS,
    RADAR_STAGES,
    TREND_CATEGORIES,
    Chunk,
    Run,
    Topic,
    TopicTimepoint,
    Trend,
    TrendAssessment,
)
from app.pipeline import run as run_module
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
    # Topic centroids are persisted for cross-run emergence; emergence itself is
    # undefined on the first run (no baseline).
    assert all(t.centroid is not None and len(t.centroid) == 384 for t in topics)
    assert all(t.emergence is None for t in trends)

    # chunks have embeddings of the configured dimension
    chunks = session.exec(select(Chunk)).all()
    assert len(chunks) == 8
    assert all(c.embedding is not None and len(c.embedding) == 384 for c in chunks)

    # at least one topic has a time series
    timepoints = session.exec(select(TopicTimepoint)).all()
    assert len(timepoints) >= 1

    # every trend gets a PESTEL/category/impact assessment with a valid radar stage
    assessments = session.exec(select(TrendAssessment)).all()
    assert len(assessments) == run.n_topics
    for a in assessments:
        assert a.pestel and all(p in PESTEL_DIMENSIONS for p in a.pestel)
        assert a.category in TREND_CATEGORIES
        assert 1.0 <= a.impact <= 10.0 and 1.0 <= a.urgency <= 10.0
        assert a.radar_stage in RADAR_STAGES


@requires_db
def test_run_pipeline_completes_with_no_documents(session):
    """An empty corpus is a valid (degenerate) run, not a crash."""
    run = run_pipeline(
        "buildings", session=session, limit=50, connector=FakeConnector([])
    )
    assert run.status == "completed"
    assert run.n_documents == 0
    assert run.n_topics == 0


@requires_db
def test_run_pipeline_rolls_back_and_persists_failed_on_db_error(session, monkeypatch):
    """A mid-pipeline DB error must roll back, persist ``failed`` + ``error``,
    and re-raise the original exception (not a PendingRollbackError)."""

    class BadEmbedder:
        dim = 999

        def embed(self, texts: list[str]) -> np.ndarray:
            return np.zeros((len(texts), 999), dtype=np.float32)

    monkeypatch.setattr(run_module, "get_embedder", lambda *a, **k: BadEmbedder())

    with pytest.raises(SQLAlchemyError):
        run_pipeline(
            "buildings", session=session, limit=50, connector=FakeConnector(_make_docs())
        )

    with Session(get_engine()) as verify:
        runs = verify.exec(select(Run).order_by(Run.id.desc())).all()
    assert runs, "the run row must be persisted"
    assert runs[0].status == "failed"
    assert runs[0].error


@requires_db
def test_emergence_is_scored_against_previous_run(session):
    docs = _make_docs()
    first = run_pipeline(
        "buildings", session=session, limit=50, connector=FakeConnector(docs)
    )
    second = run_pipeline(
        "buildings", session=session, limit=50, connector=FakeConnector(docs)
    )

    assert first.status == "completed" and second.status == "completed"
    trends = session.exec(select(Trend).where(Trend.run_id == second.id)).all()
    # The second run has the first as a baseline, so emergence is now defined and, for
    # an identical corpus, low (the topics are continuations).
    assert trends
    assert all(t.emergence is not None for t in trends)
    assert all(t.emergence < 0.2 for t in trends)
