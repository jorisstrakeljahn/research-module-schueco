"""API tests using FastAPI's TestClient against the real database."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

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
def test_start_run(client, monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(
        "app.api.routes._run_pipeline_bg",
        lambda keywords, query, limit, language="en", mode="deep_research": calls.append(
            (keywords, query, limit, language, mode)
        ),
    )

    ok = client.post(
        "/runs", json={"keywords": ["adaptive facade", "bipv"], "language": "de"}
    )
    assert ok.status_code == 202
    assert ok.json()["query"] == "adaptive facade bipv"
    assert ok.json()["language"] == "de"
    assert ok.json()["mode"] == "deep_research"
    assert calls and calls[0][0] == ["adaptive facade", "bipv"]
    assert calls[0][4] == "deep_research"

    simple = client.post(
        "/runs", json={"keywords": ["facade"], "mode": "simple"}
    )
    assert simple.status_code == 202
    assert simple.json()["mode"] == "simple"

    bad = client.post("/runs", json={"keywords": []})
    assert bad.status_code == 422


@requires_db
def test_translate_trend(client, session):
    trend = _seed(session)
    # Offline tests have no API key -> NoopTranslator -> identity output.
    resp = client.post(f"/trends/{trend.id}/translate", json={"language": "de"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["language"] == "de"
    assert body["title"] == "Adaptive facades"

    assert client.post(
        f"/trends/{trend.id}/translate", json={"language": "fr"}
    ).status_code == 422
    assert client.post(
        "/trends/999999/translate", json={"language": "de"}
    ).status_code == 404


@requires_db
def test_list_runs_respects_limit(client, session):
    for _ in range(2):
        session.add(Run(status="completed"))
    session.commit()

    runs = client.get("/runs", params={"limit": 1}).json()
    assert len(runs) == 1
    # newest first
    all_runs = client.get("/runs").json()
    assert runs[0]["id"] == max(r["id"] for r in all_runs)


@requires_db
def test_background_failure_leaves_failed_run(session, monkeypatch):
    from app.api.routes import _run_pipeline_bg

    def boom(*_a, **_k):
        raise RuntimeError("crawl exploded")

    monkeypatch.setattr("app.research.service.run_simple_search", boom)

    _run_pipeline_bg([], "facade", 10, "en", "simple")

    runs = session.exec(select(Run).order_by(Run.id.desc())).all()
    assert runs, "the background task must leave a terminal Run row"
    assert runs[0].status == "failed"
    assert runs[0].error


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
