"""Query expansion components (pluggable).

Query expansion lets the crawler discover search terms the analyst did not think of,
which is the mechanism by which the system "goes deeper" over rounds. The offline
:class:`NoopExpander` performs no expansion (deterministic, free); the
:class:`LLMQueryExpander` proposes new domain-relevant queries from what was found.
"""

from __future__ import annotations

import json
from typing import Protocol


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


class LLMQueryExpander:
    """LLM-based query expansion. Requires the ``llm`` extra and an API key."""

    def __init__(self, model_name: str = "gpt-4o-mini") -> None:
        from openai import OpenAI

        from app.config import get_settings

        self._client = OpenAI(api_key=get_settings().openai_api_key)
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
        resp = self._client.chat.completions.create(
            model=self._model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        try:
            data = json.loads(resp.choices[0].message.content)
            queries = data.get("queries", [])
        except (json.JSONDecodeError, AttributeError):
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
    if name == "openai":
        return LLMQueryExpander()
    raise ValueError(f"Unknown expander: {name!r}")
