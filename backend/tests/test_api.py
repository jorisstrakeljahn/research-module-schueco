"""API tests using FastAPI's TestClient against the real database."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.db import get_engine
from app.main import app
from app.models import Run, Topic, TopicTimepoint, Trend, TrendAssessment
from tests.conftest import requires_db


def _seed_run_with_trends(session, n: int) -> Run:
    run = Run(status="completed", n_topics=n)
    session.add(run)
    session.commit()
    session.refresh(run)
    for i in range(n):
        topic = Topic(
            run_id=run.id,
            topic_index=i,
            label=f"topic {i}",
            keywords=["facade", "envelope"],
            size=2,
            region="Europe" if i == 0 else None,
        )
        session.add(topic)
        session.commit()
        session.refresh(topic)
        trend = Trend(
            topic_id=topic.id,
            run_id=run.id,
            title=f"Trend {i}",
            summary="s",
            maturity="emerging",
        )
        session.add(trend)
        session.commit()
        session.refresh(trend)
        session.add(
            TrendAssessment(trend_id=trend.id, radar_stage="watch", pestel=["T"])
        )
    session.commit()
    return run


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
def test_start_run(client, session, monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(
        "app.api.routes._run_pipeline_bg",
        lambda *args: calls.append(args),
    )

    ok = client.post(
        "/runs", json={"keywords": ["adaptive facade", "bipv"], "language": "de"}
    )
    assert ok.status_code == 202
    assert ok.json()["query"] == "adaptive facade bipv"
    assert ok.json()["language"] == "de"
    assert ok.json()["mode"] == "deep_research"
    assert ok.json()["run_id"] > 0
    assert calls and calls[0][1] == ["adaptive facade", "bipv"]
    assert calls[0][5] == "deep_research"
    progress = client.get(f"/runs/{ok.json()['run_id']}/progress")
    assert progress.status_code == 200
    assert progress.json()["phase"] == "queued"
    assert progress.json()["events"][0]["progress"] == 2

    simple = client.post(
        "/runs", json={"keywords": ["facade"], "mode": "simple"}
    )
    assert simple.status_code == 202
    assert simple.json()["mode"] == "simple"

    capabilities = client.get("/search/capabilities")
    assert capabilities.status_code == 200
    assert any(
        source["id"] == "openalex" and source["enabled"]
        for source in capabilities.json()["sources"]
    )

    configured = client.post(
        "/runs",
        json={
            "query": "adaptive building envelopes",
            "keywords": ["vacuum glazing"],
            "region": "dach",
            "depth": "deep",
            "sources": ["openalex", "arxiv"],
        },
    )
    assert configured.status_code == 202
    assert configured.json()["query"] == "adaptive building envelopes"
    assert calls[-1][6:] == (
        ["openalex", "arxiv"],
        "dach",
        "deep",
        True,
    )
    configured_run = session.get(Run, configured.json()["run_id"])
    # Topic granularity is env-driven now (TOPIC_MAX / BERTOPIC_MIN_CLUSTER_SIZE).
    from app.config import get_settings

    settings = get_settings()
    assert configured_run.params["topic_max"] == settings.topic_max
    assert (
        configured_run.params["bertopic_min_cluster_size"]
        == settings.bertopic_min_cluster_size
    )

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
    run = Run(status="running", params={"query": "facade", "mode": "simple"})
    session.add(run)
    session.commit()
    session.refresh(run)

    _run_pipeline_bg(run.id, [], "facade", 10, "en", "simple")

    session.expire_all()
    failed = session.get(Run, run.id)
    assert failed is not None
    assert failed.status == "failed"
    assert failed.error


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


@requires_db
def test_invalid_mode_is_422(client):
    resp = client.post("/runs", json={"keywords": ["x"], "mode": "bogus"})
    assert resp.status_code == 422


@requires_db
def test_oversized_keywords_is_422(client):
    resp = client.post("/runs", json={"keywords": [f"k{i}" for i in range(11)]})
    assert resp.status_code == 422


@requires_db
def test_state_changing_route_requires_token_when_set(client, session, monkeypatch):
    from app.config import get_settings

    trend = _seed(session)
    monkeypatch.setattr(get_settings(), "api_token", "secret")

    missing = client.post(f"/trends/{trend.id}/feedback", json={"action": "confirm"})
    assert missing.status_code == 401

    ok = client.post(
        f"/trends/{trend.id}/feedback",
        json={"action": "confirm"},
        headers={"Authorization": "Bearer secret"},
    )
    assert ok.status_code == 200


@requires_db
def test_maturity_correction_persists(client, session):
    trend = _seed(session)  # seeded as "emerging"
    resp = client.post(
        f"/trends/{trend.id}/feedback",
        json={
            "action": "correct",
            "field": "maturity",
            "old_value": "emerging",
            "new_value": "established",
        },
    )
    assert resp.status_code == 200

    match = next(t for t in client.get("/trends").json() if t["id"] == trend.id)
    assert match["maturity"] == "established"


@requires_db
def test_invalid_maturity_correction_is_422(client, session):
    trend = _seed(session)
    resp = client.post(
        f"/trends/{trend.id}/feedback",
        json={"action": "correct", "field": "maturity", "new_value": "nonsense"},
    )
    assert resp.status_code == 422

    match = next(t for t in client.get("/trends").json() if t["id"] == trend.id)
    assert match["maturity"] == "emerging"


@requires_db
def test_translate_is_cached(client, session, monkeypatch):
    trend = _seed(session)

    class _CountingTranslator:
        def __init__(self) -> None:
            self.calls = 0

        def translate(self, *, title, summary, rationale, language):
            self.calls += 1
            return SimpleNamespace(
                title=f"{title} [{language}]", summary=summary, rationale=rationale
            )

    stub = _CountingTranslator()
    # routes.py binds resolve_translator at import time, so patch that reference.
    monkeypatch.setattr(
        "app.api.routes.resolve_translator", lambda settings: stub
    )

    first = client.post(f"/trends/{trend.id}/translate", json={"language": "de"})
    second = client.post(f"/trends/{trend.id}/translate", json={"language": "de"})

    assert first.status_code == 200 and second.status_code == 200
    assert first.json() == second.json()
    assert stub.calls == 1  # second request served from the persisted translation


@requires_db
def test_trends_listing_avoids_n_plus_one(client, session):
    run = _seed_run_with_trends(session, 3)

    selects: list[str] = []

    def _count(conn, cursor, statement, *args, **kwargs):
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", _count)
    try:
        resp = client.get("/trends", params={"run_id": run.id})
    finally:
        event.remove(engine, "before_cursor_execute", _count)

    assert resp.status_code == 200
    assert len(resp.json()) == 3
    # one joined select, not 1 + 2N round-trips
    assert len(selects) <= 3, f"expected no N+1, got {len(selects)} selects"


@requires_db
def test_trends_region_filter(client, session):
    run = _seed_run_with_trends(session, 3)
    europe = client.get("/trends", params={"run_id": run.id, "region": "Europe"}).json()
    assert len(europe) == 1
    assert all(t["region"] == "Europe" for t in europe)
