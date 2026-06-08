"""Tests for the evaluation overlap metric and reference-trend endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.evaluation import TrendLike, compute_overlap
from app.main import app
from app.models import Run, Topic, Trend
from tests.conftest import requires_db


def test_overlap_matches_on_shared_vocabulary() -> None:
    trends = [
        TrendLike(id=1, title="Adaptive facades", keywords=["facade", "adaptive"]),
        TrendLike(id=2, title="Quantum baking", keywords=["quantum", "oven"]),
    ]
    references = [
        TrendLike(id=10, title="Adaptive facade systems", keywords=["facade"]),
        TrendLike(id=11, title="Vertical farming", keywords=["farming", "vertical"]),
    ]
    result = compute_overlap(trends, references, threshold=0.18)

    assert result.n_matched_references == 1
    assert result.matches[0].reference_id == 10
    assert result.matches[0].trend_id == 1
    assert result.recall == 0.5
    assert result.precision == 0.5
    assert {r.id for r in result.missed_references} == {11}
    assert {t.id for t in result.novel_trends} == {2}


def test_overlap_empty_inputs() -> None:
    result = compute_overlap([], [], threshold=0.2)
    assert result.recall == 0.0
    assert result.precision == 0.0


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@requires_db
def test_reference_trend_crud_and_overlap(client, session) -> None:
    run = Run(status="completed", n_documents=1, n_topics=1)
    session.add(run)
    session.commit()
    session.refresh(run)
    topic = Topic(
        run_id=run.id, topic_index=0, label="facade", keywords=["facade", "adaptive"]
    )
    session.add(topic)
    session.commit()
    session.refresh(topic)
    trend = Trend(topic_id=topic.id, run_id=run.id, title="Adaptive facades")
    session.add(trend)
    session.commit()

    created = client.post(
        "/reference-trends",
        json={"title": "Adaptive facade systems", "keywords": ["facade"]},
    )
    assert created.status_code == 201
    ref_id = created.json()["id"]

    assert len(client.get("/reference-trends").json()) == 1

    ev = client.get("/evaluation/overlap").json()
    assert ev["n_references"] == 1
    assert ev["matched_references"] == 1
    assert ev["recall"] == 1.0
    assert len(ev["matches"]) == 1

    assert client.delete(f"/reference-trends/{ref_id}").status_code == 204
    assert len(client.get("/reference-trends").json()) == 0
