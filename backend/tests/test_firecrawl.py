"""Tests for the Firecrawl connector (mocked HTTP, no real API calls)."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.ingestion.firecrawl import FIRECRAWL_SEARCH_URL, FirecrawlConnector


def test_requires_api_key() -> None:
    with pytest.raises(ValueError):
        FirecrawlConnector(api_key="")


@respx.mock
def test_fetch_maps_results() -> None:
    respx.post(FIRECRAWL_SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "data": [
                    {
                        "url": "https://example.com/adaptive-facade",
                        "title": "New adaptive facade launched",
                        "description": "A startup unveiled a dynamic facade system.",
                        "metadata": {"publishedTime": "2025-03-01T00:00:00Z"},
                    },
                    {
                        "url": "https://example.com/empty",
                        "title": "",
                        "description": "",
                    },
                ],
            },
        )
    )
    conn = FirecrawlConnector(api_key="test-key")
    docs = conn.fetch("adaptive facade", limit=10)

    assert len(docs) == 1
    doc = docs[0]
    assert doc.title == "New adaptive facade launched"
    assert doc.source_name == "Firecrawl"
    assert doc.source_type == "news"
    assert doc.published_at is not None
    assert doc.published_at.year == 2025
