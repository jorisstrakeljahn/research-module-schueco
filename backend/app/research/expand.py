"""Query expansion components (pluggable).

Query expansion lets the crawler discover search terms the analyst did not think of,
which is the mechanism by which the system "goes deeper" over rounds. The offline
:class:`NoopExpander` performs no expansion (deterministic, free); the
:class:`LLMQueryExpander` proposes new domain-relevant queries from what was found.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from typing import Protocol

from app.llm import get_openai_client

logger = logging.getLogger(__name__)

_WORD = re.compile(r"[a-zA-Z][a-zA-Z-]{3,}")
_STOPWORDS = frozenset(
    """
    with from into over under about their there this that these those which where
    when what while will would could should shall might must have has had been
    being also more most less least very much many some such only just than then
    them they your yours ours mine between among within without across during
    before after above below again further once here both each other same study
    review analysis based using towards toward paper article research results
    """.split()
)


class QueryExpander(Protocol):
    def expand(
        self,
        domain: str,
        seeds: list[str],
        context_titles: list[str],
        already_used: list[str],
        n: int = 4,
    ) -> list[str]:
        ...


class NoopExpander:
    """No expansion. Used for deterministic, offline runs and tests."""

    def expand(
        self,
        domain: str,
        seeds: list[str],
        context_titles: list[str],
        already_used: list[str],
        n: int = 4,
    ) -> list[str]:
        return []


class KeywordExpander:
    """Offline query expansion from document titles (deterministic, no API).

    Counts meaningful adjacent word pairs (bigrams) in the titles found so far and
    proposes the most frequent ones that have not been searched yet. This lets a
    multi-round crawl actually go deeper without requiring an LLM key.
    """

    def expand(
        self,
        domain: str,
        seeds: list[str],
        context_titles: list[str],
        already_used: list[str],
        n: int = 4,
    ) -> list[str]:
        used_tokens: set[str] = set()
        for text in [*already_used, *seeds, domain]:
            used_tokens |= {w.lower() for w in _WORD.findall(text or "")}

        bigrams: Counter[tuple[str, str]] = Counter()
        for title in context_titles:
            words = [
                w.lower()
                for w in _WORD.findall(title or "")
                if w.lower() not in _STOPWORDS
            ]
            for left, right in zip(words, words[1:], strict=False):
                if left == right:
                    continue
                bigrams[(left, right)] += 1

        proposals: list[str] = []
        for (left, right), count in bigrams.most_common():
            if count < 2 or len(proposals) >= n:
                break
            # Skip pairs already covered by previous queries or the seed vocabulary.
            if left in used_tokens and right in used_tokens:
                continue
            proposals.append(f"{left} {right}")
        return proposals


class LLMQueryExpander:
    """LLM-based query expansion. Requires the ``llm`` extra and an API key."""

    def __init__(self, model_name: str = "gpt-4o-mini") -> None:
        self._client = get_openai_client()
        self._model_name = model_name

    def expand(
        self,
        domain: str,
        seeds: list[str],
        context_titles: list[str],
        already_used: list[str],
        n: int = 4,
    ) -> list[str]:
        titles = "\n".join(f"- {t}" for t in context_titles[:15])
        used = ", ".join(already_used[:40])
        prompt = (
            f"You are a foresight analyst exploring the domain: {domain}.\n"
            f"Seed terms: {', '.join(seeds)}\n"
            f"Already searched (do NOT repeat these): {used}\n"
            f"Representative documents found so far:\n{titles}\n\n"
            f"Propose {n} NEW, specific search queries (2-4 words each) that would "
            "surface adjacent or emerging sub-topics in this domain. Stay on-topic.\n"
            'Respond as JSON: {"queries": ["...", "..."]}'
        )
        try:
            resp = self._client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content)
            queries = data.get("queries", [])
        except Exception:
            # Fail open: an API error must not abort the crawl - just skip expansion.
            logger.warning("LLM query expansion failed; no expansion", exc_info=True)
            return []
        used_low = {u.lower() for u in already_used}
        return [
            q.strip()
            for q in queries
            if isinstance(q, str) and q.strip() and q.strip().lower() not in used_low
        ][:n]


def get_expander(name: str) -> QueryExpander:
    """Factory: resolve a query expander by name."""
    name = name.lower()
    if name in ("none", "noop", "off"):
        return NoopExpander()
    if name == "keyword":
        return KeywordExpander()
    if name == "openai":
        return LLMQueryExpander()
    raise ValueError(f"Unknown expander: {name!r}")
