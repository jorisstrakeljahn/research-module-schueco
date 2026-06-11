"""Tests for the deep-research layer: relevance, expansion, crawler and feedback."""

from __future__ import annotations

from app.ingestion.base import RawDocument
from app.models import ExpertFeedback, Run, Topic, Trend
from app.research.crawler import DeepResearchCrawler
from app.research.expand import LLMQueryExpander, NoopExpander
from app.research.feedback import (
    negative_terms_from_feedback,
    seeds_from_feedback,
)
from app.research.relevance import KeywordRelevance, LLMRelevance, PassthroughRelevance
from app.research.seeds import merge_seeds
from tests.conftest import requires_db


def _raising_client() -> object:
    """An OpenAI client stand-in whose completion call always fails."""

    def boom(**_: object) -> object:
        raise RuntimeError("api down")

    from types import SimpleNamespace

    return SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=boom))
    )


def _doc(i: int, title: str, source: str = "Fake") -> RawDocument:
    return RawDocument(
        external_id=f"{source}-{i}",
        title=title,
        text=title,
        url=f"http://example.org/{source}/{i}",
        source_name=source,
        source_type="science",
    )


class FakeConnector:
    source_name = "Fake"
    source_type = "science"

    def __init__(self, mapping: dict[str, list[RawDocument]]) -> None:
        self._mapping = mapping

    def fetch(self, query: str, limit: int = 50) -> list[RawDocument]:
        return self._mapping.get(query, [])[:limit]


class OneShotExpander:
    """Returns a fixed new query exactly once, to drive a second round."""

    def __init__(self, new_query: str) -> None:
        self._new_query = new_query
        self._fired = False

    def expand(self, domain, seeds, context_titles, already_used, n=4):
        if self._fired:
            return []
        self._fired = True
        return [self._new_query]


def test_merge_seeds_dedupes_case_insensitive() -> None:
    merged = merge_seeds(["Facade", "solar"], ["facade", "BIPV", ""])
    assert merged == ["Facade", "solar", "BIPV"]


def test_keyword_relevance_filters() -> None:
    rel = KeywordRelevance(include_terms=["facade building envelope"])
    docs = [
        _doc(1, "adaptive facade for buildings"),
        _doc(2, "completely unrelated cooking recipe"),
    ]
    kept = rel.keep(docs)
    assert len(kept) == 1
    assert kept[0].external_id == "Fake-1"


def test_keyword_relevance_excludes() -> None:
    rel = KeywordRelevance(
        include_terms=["facade building"],
        exclude_terms=["plastic blood"],
    )
    docs = [_doc(1, "plastic particles in human blood facade building")]
    assert rel.keep(docs) == []


def test_noop_expander_returns_nothing() -> None:
    assert NoopExpander().expand("d", ["s"], ["t"], ["u"]) == []


def test_llm_relevance_fails_open_on_api_error() -> None:
    """A dead OpenAI API must not lose documents: the gate degrades to passthrough."""
    rel = LLMRelevance.__new__(LLMRelevance)
    rel._client = _raising_client()
    rel._domain = "facades"
    rel._exclude = []
    rel._model_name = "stub"
    rel._batch_size = 20

    docs = [_doc(1, "facade a"), _doc(2, "facade b")]
    assert rel.keep(docs) == docs


def test_llm_query_expander_fails_open_on_api_error() -> None:
    """A dead OpenAI API must not abort the crawl: expansion degrades to none."""
    exp = LLMQueryExpander.__new__(LLMQueryExpander)
    exp._client = _raising_client()
    exp._model_name = "stub"

    assert exp.expand("facades", ["facade"], ["title"], ["facade"]) == []


def test_crawler_single_round_dedupes_and_passes_through() -> None:
    docs = [_doc(1, "facade a"), _doc(2, "facade b"), _doc(1, "facade a dup")]
    connector = FakeConnector({"facade": docs})
    crawler = DeepResearchCrawler(
        [connector],
        relevance=PassthroughRelevance(),
        max_rounds=1,
        max_docs=80,
    )
    result = crawler.crawl(["facade"])
    assert result.rounds == 1
    # the duplicate external id is collapsed
    assert {d.external_id for d in result.documents} == {"Fake-1", "Fake-2"}
    assert result.queries_used == ["facade"]


def test_crawler_expands_into_second_round() -> None:
    connector = FakeConnector(
        {
            "facade": [_doc(1, "facade insulation")],
            "solar glazing": [_doc(2, "solar glazing")],
        }
    )
    crawler = DeepResearchCrawler(
        [connector],
        expander=OneShotExpander("solar glazing"),
        max_rounds=3,
        max_docs=80,
    )
    result = crawler.crawl(["facade"])
    assert result.rounds == 2
    assert result.queries_used == ["facade", "solar glazing"]
    assert {d.external_id for d in result.documents} == {"Fake-1", "Fake-2"}


def test_crawler_respects_doc_budget() -> None:
    docs = [_doc(i, f"facade variant {i}") for i in range(10)]
    connector = FakeConnector({"facade": docs})
    crawler = DeepResearchCrawler(
        [connector],
        max_rounds=2,
        max_docs=3,
        per_query_limit=20,
    )
    result = crawler.crawl(["facade"])
    assert len(result.documents) == 3


@requires_db
def test_feedback_seeds_and_negatives(session) -> None:
    run = Run(status="completed")
    session.add(run)
    session.commit()
    session.refresh(run)

    def _make_trend(title: str, keywords: list[str], topic_index: int) -> Trend:
        topic = Topic(
            run_id=run.id, topic_index=topic_index, label=title, keywords=keywords
        )
        session.add(topic)
        session.commit()
        session.refresh(topic)
        trend = Trend(topic_id=topic.id, run_id=run.id, title=title)
        session.add(trend)
        session.commit()
        session.refresh(trend)
        return trend

    confirmed = _make_trend("Adaptive Facades", ["facade", "adaptive", "envelope"], 0)
    rejected = _make_trend("Plastic in Blood", ["plastic", "blood", "human"], 1)

    session.add(ExpertFeedback(trend_id=confirmed.id, action="confirm"))
    session.add(ExpertFeedback(trend_id=rejected.id, action="reject"))
    session.commit()

    seeds = seeds_from_feedback(session)
    assert "Adaptive Facades" in seeds
    assert "facade" in seeds
    assert "Plastic in Blood" not in seeds

    negatives = negative_terms_from_feedback(session)
    assert "plastic" in negatives
    assert "blood" in negatives
