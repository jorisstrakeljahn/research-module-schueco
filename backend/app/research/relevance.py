"""Relevance filtering components (pluggable, ADR-04).

A relevance gate keeps the crawl on-topic: it discards off-domain documents before
they consume the document budget or pollute clustering, and - crucially - it stops an
iterative crawler from drifting away from the domain over rounds. The offline
:class:`KeywordRelevance` uses lexical overlap; :class:`LLMRelevance` uses an LLM
judgement (batched to stay cheap).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Protocol

from app.ingestion.base import RawDocument
from app.llm import get_openai_client

logger = logging.getLogger(__name__)

_WORD = re.compile(r"[a-z]{4,}")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


class RelevanceFilter(Protocol):
    def keep(self, docs: list[RawDocument]) -> list[RawDocument]:
        ...


class PassthroughRelevance:
    """No filtering. Used when the relevance gate is disabled."""

    def keep(self, docs: list[RawDocument]) -> list[RawDocument]:
        return docs


class KeywordRelevance:
    """Lexical relevance gate: keep docs overlapping the domain, drop excluded ones.

    Offline and deterministic. A document is kept when its title+text shares at least
    one meaningful token with the domain/seed vocabulary and does not match an excluded
    (expert-rejected) term.
    """

    def __init__(
        self,
        include_terms: list[str],
        exclude_terms: list[str] | None = None,
    ) -> None:
        self._include = set()
        for term in include_terms:
            self._include |= _tokens(term)
        self._exclude = set()
        for term in exclude_terms or []:
            self._exclude |= _tokens(term)

    def keep(self, docs: list[RawDocument]) -> list[RawDocument]:
        if not self._include:
            return docs
        kept: list[RawDocument] = []
        for doc in docs:
            toks = _tokens(f"{doc.title} {doc.text}")
            if self._exclude and len(toks & self._exclude) >= 2:
                continue
            if toks & self._include:
                kept.append(doc)
        return kept


class LLMRelevance:
    """LLM-based relevance gate. Requires the ``llm`` extra and an API key."""

    def __init__(
        self,
        domain: str,
        exclude_terms: list[str] | None = None,
        model_name: str = "gpt-4o-mini",
        batch_size: int = 20,
    ) -> None:
        self._client = get_openai_client()
        self._domain = domain
        self._exclude = exclude_terms or []
        self._model_name = model_name
        self._batch_size = batch_size

    def _judge_batch(self, docs: list[RawDocument]) -> list[RawDocument]:
        listing = "\n".join(f"{i}. {d.title}" for i, d in enumerate(docs))
        exclude = (
            f"Explicitly NOT relevant (reject): {', '.join(self._exclude)}.\n"
            if self._exclude
            else ""
        )
        prompt = (
            f"Domain of interest: {self._domain}.\n{exclude}"
            "From the numbered titles below, return the indices that are relevant to "
            "the domain. Be inclusive of adjacent technical topics but exclude clearly "
            f"unrelated ones.\n{listing}\n\n"
            'Respond as JSON: {"relevant": [0, 2, ...]}'
        )
        try:
            resp = self._client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content)
            idxs = {int(i) for i in data.get("relevant", [])}
        except Exception:
            # Fail open: a dead/erroring API or an unparseable response must never
            # abort the crawl or silently drop documents - degrade to passthrough.
            logger.warning("LLM relevance gate failed; keeping batch", exc_info=True)
            return docs
        return [d for i, d in enumerate(docs) if i in idxs]

    def keep(self, docs: list[RawDocument]) -> list[RawDocument]:
        kept: list[RawDocument] = []
        for start in range(0, len(docs), self._batch_size):
            kept.extend(self._judge_batch(docs[start : start + self._batch_size]))
        return kept


def get_relevance(
    name: str,
    *,
    domain: str = "",
    include_terms: list[str] | None = None,
    exclude_terms: list[str] | None = None,
) -> RelevanceFilter:
    """Factory: resolve a relevance filter by name."""
    name = name.lower()
    if name in ("off", "none", "passthrough"):
        return PassthroughRelevance()
    if name == "keyword":
        terms = list(include_terms or [])
        if domain:
            terms.append(domain)
        return KeywordRelevance(include_terms=terms, exclude_terms=exclude_terms)
    if name == "openai":
        return LLMRelevance(domain=domain, exclude_terms=exclude_terms)
    raise ValueError(f"Unknown relevance filter: {name!r}")
