"""API tests using FastAPI's TestClient against the real database."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Run, Topic, TopicTimepoint, Trend, TrendAssessment
from tests.conftest import requires_db


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _seed(session) -> Trend:
    run = Run(status="completed", n_documents=3, n_topics=1, embedder="hashing")
    session.add(run)
    session.commit()
    session.refresh(run)

    topic = Topic(
        run_id=run.id,
        topic_index=0,
        label="facade, adaptive",
        keywords=["facade", "adaptive", "envelope"],
        size=3,
    )
    session.add(topic)
    session.commit()
    session.refresh(topic)

    session.add(TopicTimepoint(topic_id=topic.id, period="2023-Q1", doc_count=2))
    session.add(TopicTimepoint(topic_id=topic.id, period="2024-Q1", doc_count=1))

    trend = Trend(
        topic_id=topic.id,
        run_id=run.id,
        title="Adaptive facades",
        summary="A trend about adaptive facades.",
        maturity="emerging",
        evidence=[{"title": "Paper A", "url": "http://x/a"}],
    )
    session.add(trend)
    session.commit()
    session.refresh(trend)
    session.add(TrendAssessment(trend_id=trend.id, radar_stage="watch", pestel=["T"]))
    session.commit()
    return trend


@requires_db
def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@requires_db
def test_list_and_get_trends(client, session):
    trend = _seed(session)

    runs = client.get("/runs").json()
    assert any(r["id"] == trend.run_id for r in runs)

    trends = client.get("/trends").json()
    assert len(trends) == 1
    assert trends[0]["title"] == "Adaptive facades"
    assert trends[0]["keywords"] == ["facade", "adaptive", "envelope"]
    assert trends[0]["radar_stage"] == "watch"

    detail = client.get(f"/trends/{trend.id}").json()
    assert detail["maturity"] == "emerging"
    assert len(detail["timeseries"]) == 2
    assert detail["timeseries"][0]["period"] == "2023-Q1"
    assert detail["evidence"][0]["url"] == "http://x/a"


@requires_db
def test_maturity_filter(client, session):
    _seed(session)
    assert len(client.get("/trends", params={"maturity": "emerging"}).json()) == 1
    assert len(client.get("/trends", params={"maturity": "megatrend"}).json()) == 0


@requires_db
def test_feedback(client, session):
    trend = _seed(session)
    resp = client.post(
        f"/trends/{trend.id}/feedback",
        json={"action": "correct", "field": "maturity", "new_value": "established"},
    )
    assert resp.status_code == 200
    assert resp.json()["action"] == "correct"

    bad = client.post(f"/trends/{trend.id}/feedback", json={"action": "bogus"})
    assert bad.status_code == 422

    missing = client.get("/trends/999999")
    assert missing.status_code == 404
