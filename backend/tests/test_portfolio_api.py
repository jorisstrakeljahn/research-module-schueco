"""Phase 6 portfolio, run-diff and review-queue API contract tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app.main import app
from app.models import (
    CanonicalTrend,
    Run,
    Topic,
    TopicTimepoint,
    Trend,
    TrendAssessment,
    TrendDecision,
    TrendOccurrence,
)
from tests.conftest import requires_db


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _add_snapshot(
    session,
    *,
    run: Run,
    index: int,
    title: str,
    size: int,
    maturity: str,
    evidence_title: str,
) -> Trend:
    topic = Topic(
        run_id=run.id,
        topic_index=index,
        label=title,
        keywords=["facade", f"run-{run.id}"],
        size=size,
        region="Europe",
        country="DE",
    )
    session.add(topic)
    session.commit()
    session.refresh(topic)
    session.add(TopicTimepoint(topic_id=topic.id, period="2026-Q1", doc_count=size))
    trend = Trend(
        topic_id=topic.id,
        run_id=run.id,
        title=title,
        summary=f"{title} summary",
        maturity=maturity,
        emergence=0.7,
        evidence=[
            {
                "title": evidence_title,
                "url": f"https://example.test/{run.id}",
                "source": "Test source",
                "published_at": "2026-07-01",
            }
        ],
    )
    session.add(trend)
    session.commit()
    session.refresh(trend)
    session.add(
        TrendAssessment(
            trend_id=trend.id,
            pestel=["technological"],
            category="technology",
            impact=8,
            urgency=7,
            uncertainty=3,
            radar_stage="act",
            rationale=f"Rationale for {title}",
        )
    )
    session.commit()
    return trend


def _seed_portfolio(session) -> tuple[CanonicalTrend, CanonicalTrend, TrendOccurrence]:
    first_run = Run(status="completed", n_documents=2, n_topics=1)
    second_run = Run(status="completed", n_documents=4, n_topics=1)
    session.add(first_run)
    session.add(second_run)
    session.commit()
    session.refresh(first_run)
    session.refresh(second_run)
    first = _add_snapshot(
        session,
        run=first_run,
        index=0,
        title="Adaptive facades",
        size=2,
        maturity="emerging",
        evidence_title="First paper",
    )
    latest = _add_snapshot(
        session,
        run=second_run,
        index=0,
        title="Adaptive building envelopes",
        size=4,
        maturity="established",
        evidence_title="Latest paper",
    )
    canonical = CanonicalTrend(
        id="canonical-main",
        title=latest.title,
        summary=latest.summary,
        maturity=latest.maturity,
        pestel=["technological"],
        category="technology",
        impact=8,
        urgency=7,
        uncertainty=3,
        radar_stage="act",
        first_run_id=first_run.id,
        last_run_id=second_run.id,
    )
    target = CanonicalTrend(
        id="canonical-target",
        title="Target trend",
        summary="Target summary",
        maturity="emerging",
        first_run_id=first_run.id,
        last_run_id=first_run.id,
    )
    session.add(canonical)
    session.add(target)
    session.commit()
    session.add(
        TrendOccurrence(
            canonical_trend_id=canonical.id,
            trend_id=first.id,
            run_id=first_run.id,
            change_type="new",
            changed_fields=["title", "summary", "maturity"],
            review_status="approved",
        )
    )
    review = TrendOccurrence(
        canonical_trend_id=canonical.id,
        trend_id=latest.id,
        run_id=second_run.id,
        change_type="classification_changed",
        match_score=0.74,
        match_margin=0.03,
        changed_fields=["title", "maturity"],
        review_status="pending",
        review_reasons=[{"code": "ambiguous_match", "kind": "identity"}],
        review_reason="ambiguous_match",
        evidence_added_count=2,
        evidence_removed_count=1,
        prevalence=0.5,
    )
    session.add(review)
    session.commit()
    session.refresh(review)
    return canonical, target, review


@requires_db
def test_portfolio_read_contracts(client, session):
    canonical, _, review = _seed_portfolio(session)

    listing = client.get("/portfolio/trends").json()
    item = next(item for item in listing if item["id"] == canonical.id)
    assert item["keywords"] == ["facade", f"run-{review.run_id}"]
    assert item["size"] == 4
    assert item["occurrence_count"] == 2
    assert item["status"] == "active"
    assert item["first_run_id"] < item["last_run_id"]

    detail = client.get(f"/portfolio/trends/{canonical.id}")
    assert detail.status_code == 200
    assert detail.json()["rationale"] == "Rationale for Adaptive building envelopes"
    assert detail.json()["evidence"][0]["title"] == "Latest paper"
    assert detail.json()["evidence"][0]["run_id"] == review.run_id
    assert detail.json()["timeseries"] == [{"period": "2026-Q1", "doc_count": 4}]

    pestel = client.get(
        f"/portfolio/trends/{canonical.id}/pestel-analysis"
    ).json()
    assert pestel["trend_id"] == canonical.id
    assert pestel["run_id"] == review.run_id
    assert [item["dimension"] for item in pestel["dimensions"]] == [
        "political",
        "economic",
        "social",
        "technological",
        "environmental",
        "legal",
    ]
    assert all(item["total_documents"] == 1 for item in pestel["dimensions"])

    history = client.get(f"/portfolio/trends/{canonical.id}/history").json()
    assert history["trend_id"] == canonical.id
    assert [point["change_type"] for point in history["points"]] == [
        "new",
        "classification_changed",
    ]
    assert {evidence["title"] for evidence in history["evidence"]} == {
        "First paper",
        "Latest paper",
    }
    assert history["decisions"] == []

    diff = client.get(f"/runs/{review.run_id}/diff").json()
    assert diff["counts"] == {
        "new": 0,
        "classification_changed": 1,
        "content_changed": 0,
        "evidence_only": 0,
        "unchanged": 0,
    }
    assert diff["entries"][0]["before"]["title"] == "Adaptive facades"
    assert diff["entries"][0]["after"]["title"] == "Adaptive building envelopes"
    assert diff["entries"][0]["margin"] == 0.03

    queue = client.get("/review-queue").json()
    assert queue == [
        {
            "occurrence_id": review.id,
            "run_id": review.run_id,
            "canonical_trend_id": canonical.id,
            "title": "Adaptive building envelopes",
            "summary": "Adaptive building envelopes summary",
            "maturity": "established",
            "match_score": 0.74,
            "margin": 0.03,
            "change_type": "classification_changed",
            "review_status": "pending",
            "review_reasons": [{"code": "ambiguous_match", "kind": "identity"}],
            "changed_fields": ["title", "maturity"],
            "evidence_added_count": 2,
            "evidence_removed_count": 1,
            "prevalence": 0.5,
            "reason": "ambiguous_match",
            "suggested_trend": {
                "id": canonical.id,
                "title": "Adaptive building envelopes",
                "status": "active",
            },
            "candidates": [],
        }
    ]
    assert client.get("/review-queue", params={"run_id": review.run_id - 1}).json() == []
    run_item = next(item for item in client.get("/runs").json() if item["id"] == review.run_id)
    assert run_item["change_counts"] == {"classification_changed": 1}
    assert run_item["review_counts"] == {"pending": 1}


@requires_db
def test_classification_review_confirm_applies_staged_values(client, session):
    canonical, _, review = _seed_portfolio(session)
    canonical.title = "Previously approved title"
    review.review_reasons = [
        {
            "code": "material_change",
            "kind": "classification",
            "field": "title",
            "before": canonical.title,
            "after": "Adaptive building envelopes",
        }
    ]
    review.review_reason = "material_change"
    session.add(canonical)
    session.add(review)
    session.commit()

    response = client.post(
        f"/review-queue/{review.id}/decision",
        json={
            "action": "confirm",
            "reviewer": "reviewer@example.test",
            "reason": "Classification is correct",
            "idempotency_key": "classification-confirm-1",
        },
    )

    assert response.status_code == 200
    session.expire_all()
    assert session.get(CanonicalTrend, canonical.id).title == "Adaptive building envelopes"
    assert session.get(TrendOccurrence, review.id).review_status == "approved"


@requires_db
def test_new_trend_is_created_only_after_confirmation(client, session):
    run = Run(status="completed", n_documents=1, n_topics=1)
    session.add(run)
    session.commit()
    session.refresh(run)
    trend = _add_snapshot(
        session,
        run=run,
        index=0,
        title="Novel facade signal",
        size=1,
        maturity="weak_signal",
        evidence_title="Novel evidence",
    )
    occurrence = TrendOccurrence(
        trend_id=trend.id,
        run_id=run.id,
        change_type="new",
        review_status="pending",
        review_reasons=[{"code": "new_trend", "kind": "classification"}],
        changed_fields=["title", "summary", "maturity"],
    )
    session.add(occurrence)
    session.commit()
    session.refresh(occurrence)
    assert occurrence.canonical_trend_id is None

    response = client.post(
        f"/review-queue/{occurrence.id}/decision",
        json={
            "action": "confirm",
            "reviewer": "reviewer@example.test",
            "reason": "Accept new trend",
            "idempotency_key": "new-confirm-1",
        },
    )

    assert response.status_code == 200
    session.expire_all()
    resolved = session.get(TrendOccurrence, occurrence.id)
    assert resolved.review_status == "approved"
    canonical = session.get(CanonicalTrend, resolved.canonical_trend_id)
    assert canonical.title == "Novel facade signal"
    assert canonical.status == "active"


@requires_db
def test_new_trend_can_be_linked_to_existing_trend(client, session):
    _, target, _ = _seed_portfolio(session)
    run = Run(status="completed", n_documents=1, n_topics=1)
    session.add(run)
    session.commit()
    session.refresh(run)
    trend = _add_snapshot(
        session,
        run=run,
        index=0,
        title="Looks new but is not",
        size=1,
        maturity="weak_signal",
        evidence_title="Duplicate evidence",
    )
    occurrence = TrendOccurrence(
        trend_id=trend.id,
        run_id=run.id,
        change_type="new",
        review_status="pending",
        review_reasons=[{"code": "new_trend", "kind": "classification"}],
        changed_fields=["title", "summary", "maturity"],
    )
    session.add(occurrence)
    session.commit()
    session.refresh(occurrence)

    response = client.post(
        f"/review-queue/{occurrence.id}/decision",
        json={
            "action": "link",
            "reviewer": "reviewer@example.test",
            "reason": "Duplicate of existing trend",
            "canonical_trend_id": target.id,
            "idempotency_key": "new-link-1",
        },
    )

    assert response.status_code == 200
    session.expire_all()
    resolved = session.get(TrendOccurrence, occurrence.id)
    assert resolved.review_status == "approved"
    assert resolved.canonical_trend_id == target.id
    # Linking must not overwrite the curated content of the target trend.
    linked = session.get(CanonicalTrend, target.id)
    assert linked.title == "Target trend"


@requires_db
def test_portfolio_decisions_are_applied_and_idempotent(client, session):
    canonical, target, _ = _seed_portfolio(session)
    correction = {
        "action": "correct",
        "reviewer": "reviewer@example.test",
        "reason": "Expert correction",
        "changes": {"title": "Corrected title", "unsupported": "ignored"},
        "idempotency_key": "portfolio-correct-1",
    }
    first = client.post(f"/portfolio/trends/{canonical.id}/decisions", json=correction)
    repeated = client.post(f"/portfolio/trends/{canonical.id}/decisions", json=correction)
    assert first.status_code == 200
    assert repeated.json()["id"] == first.json()["id"]
    assert first.json()["before"]["title"] == "Adaptive building envelopes"
    assert first.json()["after"]["title"] == "Corrected title"
    assert client.get(f"/portfolio/trends/{canonical.id}").json()["title"] == "Corrected title"

    merge = client.post(
        f"/portfolio/trends/{canonical.id}/decisions",
        json={
            "action": "merge",
            "reviewer": "reviewer@example.test",
            "reason": "Duplicate",
            "target_trend_id": target.id,
            "idempotency_key": "portfolio-merge-1",
        },
    )
    assert merge.status_code == 200
    merged = session.get(CanonicalTrend, canonical.id)
    session.refresh(merged)
    assert merged.status == "merged"
    assert merged.merged_into_id == target.id
    assert len(session.exec(select(TrendDecision)).all()) == 2


@requires_db
@pytest.mark.parametrize("action", ["link", "create", "reject", "merge"])
def test_review_actions_resolve_queue_append_only(client, session, action):
    canonical, target, review = _seed_portfolio(session)
    payload = {
        "action": action,
        "reviewer": "reviewer@example.test",
        "reason": f"Resolve by {action}",
        "idempotency_key": f"review-{action}-1",
    }
    if action == "link":
        payload["canonical_trend_id"] = target.id
    elif action == "merge":
        payload["target_trend_id"] = target.id

    first = client.post(f"/review-queue/{review.id}/decision", json=payload)
    repeated = client.post(f"/review-queue/{review.id}/decision", json=payload)
    assert first.status_code == 200
    assert repeated.status_code == 200
    assert repeated.json()["id"] == first.json()["id"]
    assert client.get("/review-queue").json() == []

    session.expire_all()
    resolved = session.get(TrendOccurrence, review.id)
    assert resolved.change_type == "classification_changed"
    assert resolved.review_status in {"approved", "rejected"}
    assert resolved.review_reason == "ambiguous_match"
    decisions = session.exec(
        select(TrendDecision).where(TrendDecision.occurrence_id == review.id)
    ).all()
    assert len(decisions) == 1
    assert decisions[0].action == action

    source = session.get(CanonicalTrend, canonical.id)
    if action == "reject":
        assert source.status == "active"
    elif action == "merge":
        assert source.status == "merged"
        assert source.merged_into_id == target.id
        assert resolved.canonical_trend_id == target.id
    elif action == "link":
        assert resolved.canonical_trend_id == target.id
    else:
        created = session.get(CanonicalTrend, resolved.canonical_trend_id)
        assert created is not None
        assert created.id not in {canonical.id, target.id}
        assert created.status == "active"


@requires_db
def test_portfolio_api_validation_and_missing_resources(client, session):
    canonical, _, review = _seed_portfolio(session)
    assert client.get("/portfolio/trends/missing").status_code == 404
    assert client.get("/runs/999999/diff").status_code == 404
    assert client.post(
        f"/portfolio/trends/{canonical.id}/decisions",
        json={
            "action": "merge",
            "reviewer": "r",
            "reason": "invalid",
            "target_trend_id": canonical.id,
            "idempotency_key": "self-merge",
        },
    ).status_code == 422
    assert client.post(
        f"/review-queue/{review.id}/decision",
        json={
            "action": "link",
            "reviewer": "r",
            "reason": "missing target",
            "idempotency_key": "missing-target",
        },
    ).status_code == 422
