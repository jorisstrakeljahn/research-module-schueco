"""Trend description components (pluggable).

The offline :class:`TemplateDescriber` produces a deterministic, source-grounded
description without any LLM. :class:`OpenAIDescriber` uses an LLM with RAG-style
grounding (the representative documents are passed as context) and is the scientific
default once the ``llm`` extra and an API key are available (ADR-11).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol


@dataclass
class TrendDescription:
    title: str
    summary: str
    evidence: list[dict]


_LANGUAGE_NAMES = {"de": "German", "en": "English"}


class Describer(Protocol):
    def describe(
        self, keywords: list[str], representative: list[dict], language: str = "en"
    ) -> TrendDescription:
        ...


def _evidence(representative: list[dict]) -> list[dict]:
    return [
        {"title": r.get("title", ""), "url": r.get("url")}
        for r in representative
        if r.get("title")
    ]


class TemplateDescriber:
    """Deterministic, offline description grounded in the representative sources."""

    def describe(
        self, keywords: list[str], representative: list[dict], language: str = "en"
    ) -> TrendDescription:
        kws = [k for k in keywords if k]
        title = ", ".join(w.capitalize() for w in kws[:3]) if kws else "Unlabeled trend"
        titles = [r.get("title", "") for r in representative[:3] if r.get("title")]
        focus = ", ".join(kws[:5]) if kws else "the clustered documents"
        summary = f"This trend centers on {focus}."
        if titles:
            summary += " Representative sources: " + "; ".join(titles) + "."
        return TrendDescription(title=title, summary=summary, evidence=_evidence(representative))


class OpenAIDescriber:
    """LLM-based, RAG-grounded description. Requires ``llm`` extra and an API key."""

    def __init__(self, model_name: str = "gpt-4o-mini") -> None:
        from openai import OpenAI

        from app.config import get_settings

        self._client = OpenAI(api_key=get_settings().openai_api_key)
        self._model_name = model_name

    def describe(
        self, keywords: list[str], representative: list[dict], language: str = "en"
    ) -> TrendDescription:
        context = "\n".join(
            f"- {r.get('title', '')}: {r.get('text', '')[:400]}"
            for r in representative[:6]
        )
        lang_name = _LANGUAGE_NAMES.get(language, "English")
        prompt = (
            "You are a foresight analyst. Based ONLY on the sources below, write a "
            "concise trend title (max 8 words) and a 2-3 sentence summary. "
            f"Write the title and summary in {lang_name}. "
            "Do not invent facts beyond the sources.\n"
            f"Keywords: {', '.join(keywords)}\nSources:\n{context}\n\n"
            'Respond as JSON: {"title": "...", "summary": "..."}'
        )
        resp = self._client.chat.completions.create(
            model=self._model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        return TrendDescription(
            title=data.get("title", "").strip() or "Unlabeled trend",
            summary=data.get("summary", "").strip(),
            evidence=_evidence(representative),
        )


def get_describer(name: str) -> Describer:
    """Factory: resolve a describer by name."""
    name = name.lower()
    if name == "template":
        return TemplateDescriber()
    if name == "openai":
        return OpenAIDescriber()
    raise ValueError(f"Unknown describer: {name!r}")
