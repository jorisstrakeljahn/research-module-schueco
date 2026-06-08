"""On-demand translation of generated trend text (DE/EN).

Trend titles/summaries are written in the run's output language (ADR-28). This module
adds *post-hoc* translation so an analyst can read any existing trend in the other
language without re-running the pipeline. :class:`OpenAITranslator` uses the LLM with a
fixed JSON schema; :class:`NoopTranslator` is the offline identity fallback so the
endpoint never hard-fails when no API key is configured.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

_LANGUAGE_NAMES = {"de": "German", "en": "English"}


@dataclass
class TranslatedTrend:
    title: str
    summary: str
    rationale: str | None = None


class Translator(Protocol):
    def translate(
        self, *, title: str, summary: str, rationale: str | None, language: str
    ) -> TranslatedTrend:
        ...


class NoopTranslator:
    """Identity translation (used when no LLM is available)."""

    def translate(
        self, *, title: str, summary: str, rationale: str | None, language: str
    ) -> TranslatedTrend:
        return TranslatedTrend(title=title, summary=summary, rationale=rationale)


class OpenAITranslator:
    """LLM translation with a fixed JSON schema. Requires an API key."""

    def __init__(self, model_name: str = "gpt-4o-mini") -> None:
        from openai import OpenAI

        from app.config import get_settings

        self._client = OpenAI(api_key=get_settings().openai_api_key)
        self._model_name = model_name
        self._fallback = NoopTranslator()

    def translate(
        self, *, title: str, summary: str, rationale: str | None, language: str
    ) -> TranslatedTrend:
        lang_name = _LANGUAGE_NAMES.get(language, "English")
        payload = {"title": title, "summary": summary, "rationale": rationale or ""}
        prompt = (
            f"Translate the following foresight trend fields into {lang_name}. "
            "Keep domain terms and proper nouns natural; do not add or remove content. "
            f"Input JSON:\n{json.dumps(payload, ensure_ascii=False)}\n\n"
            'Respond as JSON with the same keys: {"title": "...", "summary": "...", '
            '"rationale": "..."}'
        )
        try:
            resp = self._client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content)
        except Exception:
            return self._fallback.translate(
                title=title, summary=summary, rationale=rationale, language=language
            )
        return TranslatedTrend(
            title=str(data.get("title") or title).strip(),
            summary=str(data.get("summary") or summary).strip(),
            rationale=(str(data.get("rationale")).strip() or None)
            if data.get("rationale")
            else rationale,
        )


def get_translator(name: str) -> Translator:
    """Factory: resolve a translator by name (``openai`` | ``none``)."""
    name = (name or "").lower()
    if name == "openai":
        return OpenAITranslator()
    if name in ("none", "noop", "off", "template"):
        return NoopTranslator()
    raise ValueError(f"Unknown translator: {name!r}")


def resolve_translator(settings) -> Translator:
    """Pick a translator from settings; ``auto`` uses OpenAI iff an API key is set."""
    name = (settings.translator or "auto").lower()
    if name == "auto":
        name = "openai" if settings.openai_api_key else "none"
    return get_translator(name)
