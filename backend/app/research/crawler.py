"""Deep-research crawler: bounded focused crawling / snowball sampling (ADR-22).

The crawler runs for a fixed number of rounds. Each round it:
  1. fetches documents for the current query frontier from every connector,
  2. de-duplicates them (by external id / url / title),
  3. applies the relevance gate, and
  4. expands the frontier with new queries derived from what was found.

It is bounded by ``max_rounds``, a global ``max_docs`` budget and a
``per_query_limit`` so it stays cheap, terminates deterministically, and cannot run
away - the controlled design discussed with the user.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.ingestion.base import Connector, RawDocument, doc_key
from app.research.expand import NoopExpander, QueryExpander
from app.research.relevance import PassthroughRelevance, RelevanceFilter

# Called with (event_name, details) as the crawl progresses, e.g.
# ("source_searched", {"source": "OpenAlex", "query": "...", "findings": 12}).
CrawlObserver = Callable[[str, dict[str, Any]], None]


@dataclass
class CrawlResult:
    documents: list[RawDocument]
    queries_used: list[str] = field(default_factory=list)
    rounds: int = 0


class DeepResearchCrawler:
    """Iterative, bounded multi-source crawler with relevance gating and expansion."""

    def __init__(
        self,
        connectors: list[Connector],
        *,
        expander: QueryExpander | None = None,
        relevance: RelevanceFilter | None = None,
        domain: str = "",
        max_rounds: int = 2,
        max_docs: int = 80,
        per_query_limit: int = 20,
        expand_terms: int = 4,
        observer: CrawlObserver | None = None,
    ) -> None:
        self.connectors = connectors
        self.expander = expander or NoopExpander()
        self.relevance = relevance or PassthroughRelevance()
        self.domain = domain
        self.max_rounds = max(1, max_rounds)
        self.max_docs = max(1, max_docs)
        self.per_query_limit = max(1, per_query_limit)
        self.expand_terms = max(0, expand_terms)
        self._observer = observer

    def _notify(self, event: str, details: dict) -> None:
        if self._observer:
            try:
                self._observer(event, details)
            except Exception:  # observers must never break the crawl
                pass

    def crawl(self, seeds: list[str]) -> CrawlResult:
        frontier: list[str] = [s.strip() for s in seeds if s and s.strip()]
        used: list[str] = []
        used_set: set[str] = set()
        collected: dict[str, RawDocument] = {}
        rounds_done = 0

        for round_index in range(self.max_rounds):
            pending = [q for q in frontier if q.lower() not in used_set]
            if not pending or len(collected) >= self.max_docs:
                break
            rounds_done += 1
            self._notify(
                "round_started",
                {"round": rounds_done, "queries": list(pending)},
            )

            # 1. fetch
            fetched: list[RawDocument] = []
            for query in pending:
                used.append(query)
                used_set.add(query.lower())
                for connector in self.connectors:
                    try:
                        found = connector.fetch(query, limit=self.per_query_limit)
                    except Exception:
                        self._notify(
                            "source_failed",
                            {
                                "source": getattr(
                                    connector, "source_name", type(connector).__name__
                                ),
                                "query": query,
                            },
                        )
                        continue
                    fetched.extend(found)
                    self._notify(
                        "source_searched",
                        {
                            "source": getattr(
                                connector, "source_name", type(connector).__name__
                            ),
                            "source_type": getattr(connector, "source_type", None),
                            "query": query,
                            "findings": len(found),
                        },
                    )

            # 2. de-duplicate (within batch and against already-collected)
            unique: list[RawDocument] = []
            seen = set(collected.keys())
            for doc in fetched:
                key = doc_key(doc)
                if not key or key in seen:
                    continue
                seen.add(key)
                unique.append(doc)

            # 3. relevance gate
            kept = self.relevance.keep(unique)
            for doc in kept:
                if len(collected) >= self.max_docs:
                    break
                collected[doc_key(doc)] = doc
            self._notify(
                "round_completed",
                {
                    "round": rounds_done,
                    "unique": len(unique),
                    "kept": len(kept),
                    "total": len(collected),
                },
            )

            # 4. expand the frontier for the next round
            if round_index < self.max_rounds - 1 and len(collected) < self.max_docs:
                titles = [d.title for d in collected.values()]
                new_terms = self.expander.expand(
                    self.domain, seeds, titles, used, n=self.expand_terms
                )
                added = []
                for term in new_terms:
                    if term.lower() not in used_set and term not in frontier:
                        frontier.append(term)
                        added.append(term)
                if added:
                    self._notify("queries_expanded", {"queries": added})

        documents = list(collected.values())[: self.max_docs]
        return CrawlResult(documents=documents, queries_used=used, rounds=rounds_done)
