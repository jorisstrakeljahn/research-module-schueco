"""Tests for the shared research service (simple + deep-research entry points)."""

from __future__ import annotations

from app.config import get_settings
from app.ingestion.base import RawDocument
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
