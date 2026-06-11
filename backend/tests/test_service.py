"""Tests for the shared research service (simple + deep-research entry points)."""

from __future__ import annotations

from app.config import get_settings
from app.ingestion.base import RawDocument
from app.models import ExpertFeedback, Run, Topic, Trend
from app.research.service import run_deep_research, run_simple_search
from tests.conftest import requires_db


class FakeConnector:
    source_name = "Fake"
    source_type = "science"

    def __init__(self, docs: list[RawDocument]) -> None:
        self._docs = docs

    def fetch(self, query: str, limit: int = 50) -> list[RawDocument]:
        return self._docs[:limit]


def _docs() -> list[RawDocument]:
    return [
        RawDocument(
            external_id=f"fake-{i}",
            title=f"adaptive facade study {i}",
            text=f"adaptive facade envelope study number {i}",
            url=f"http://example.org/{i}",
            source_name="Fake",
            source_type="science",
        )
        for i in range(3)
    ]


@requires_db
def test_run_simple_search_persists_run(session) -> None:
    connector = FakeConnector(_docs())
    run = run_simple_search(
        "adaptive facade", session=session, connectors=[connector]
    )
    assert run.status == "completed"
    assert run.n_documents == 3
    assert run.params["mode"] == "simple"


@requires_db
def test_run_deep_research_persists_run(session) -> None:
    connector = FakeConnector(_docs())
    outcome = run_deep_research(
        session=session,
        seeds=["adaptive facade"],
        settings=get_settings(),
        use_feedback=False,
        connectors=[connector],
    )
    assert outcome.run.status == "completed"
    assert outcome.run.n_documents == 3
    assert outcome.run.params["mode"] == "deep_research"
    assert outcome.rounds >= 1
    assert "adaptive facade" in outcome.seeds


@requires_db
def test_rejection_filters_next_crawl(session) -> None:
    """A rejected trend's vocabulary must steer the next crawl even with the default
    RELEVANCE=off (the gate escalates to keyword filtering when excludes exist)."""
    run = Run(status="completed")
    session.add(run)
    session.commit()
    session.refresh(run)

    topic = Topic(
        run_id=run.id,
        topic_index=0,
        label="crypto",
        keywords=["blockchain", "cryptocurrency", "ledger"],
    )
    session.add(topic)
    session.commit()
    session.refresh(topic)

    trend = Trend(topic_id=topic.id, run_id=run.id, title="Blockchain hype")
    session.add(trend)
    session.commit()
    session.refresh(trend)

    session.add(ExpertFeedback(trend_id=trend.id, action="reject"))
    session.commit()

    on_domain = RawDocument(
        external_id="ok-1",
        title="adaptive facade envelope",
        text="adaptive facade envelope retrofit",
        url="http://example.org/ok",
        source_name="Fake",
        source_type="science",
    )
    rejected = RawDocument(
        external_id="bad-1",
        title="blockchain cryptocurrency ledger",
        text="blockchain cryptocurrency distributed ledger token",
        url="http://example.org/bad",
        source_name="Fake",
        source_type="science",
    )
    connector = FakeConnector([on_domain, rejected])

    outcome = run_deep_research(
        session=session,
        seeds=["adaptive facade"],
        settings=get_settings(),
        use_feedback=True,
        connectors=[connector],
    )
    assert outcome.run.n_documents == 1
