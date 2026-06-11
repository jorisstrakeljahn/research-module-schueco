"""Shared OpenAI client construction.

Single place that wires the API key (and, later, base URL / timeout) so a config
change is one edit instead of six. The ``openai`` import is deferred into the
function body so importing this module never requires the optional ``llm`` extra.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai import OpenAI


def get_openai_client() -> OpenAI:
    """Construct an OpenAI client from the configured API key."""
    from openai import OpenAI

    from app.config import get_settings

    return OpenAI(api_key=get_settings().openai_api_key)
