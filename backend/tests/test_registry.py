"""Tests for the connector registry (source selection, Firecrawl gating)."""

from __future__ import annotations

from app.config import Settings
from app.ingestion.firecrawl import FirecrawlConnector
from app.ingestion.registry import build_connectors


def test_firecrawl_skipped_without_key() -> None:
    settings = Settings(sources="firecrawl", firecrawl_api_key="")
    connectors = build_connectors(settings=settings)
    # No key -> firecrawl skipped -> registry falls back to OpenAlex.
    assert all(not isinstance(c, FirecrawlConnector) for c in connectors)
    assert connectors  # never empty


def test_firecrawl_web_is_weak_signal_web_source() -> None:
    settings = Settings(sources="firecrawl_web", firecrawl_api_key="key")
    connectors = build_connectors(settings=settings)
    fire = [c for c in connectors if isinstance(c, FirecrawlConnector)]
    assert len(fire) == 1
    assert fire[0].source_type == "web"


def test_news_and_web_can_coexist() -> None:
    settings = Settings(sources="firecrawl,firecrawl_web", firecrawl_api_key="key")
    connectors = build_connectors(settings=settings)
    types = {c.source_type for c in connectors if isinstance(c, FirecrawlConnector)}
    assert types == {"news", "web"}
