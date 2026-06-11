"""Firecrawl connector (web / news / blogs).

Firecrawl (https://firecrawl.dev) offers a hosted search+scrape API that returns
clean, LLM-ready text for arbitrary web pages. It requires an API key. Web sources
are the fastest-moving signals and map to the ``weak_signal``/``emerging`` end of the
trend-maturity spectrum (ADR-20).

The parsing is intentionally defensive so the connector keeps working across minor
response-shape changes; if no API key is configured it is skipped by the registry.
"""

from __future__ import annotations

import httpx

from app.ingestion.base import RawDocument, parse_date

FIRECRAWL_SEARCH_URL = "https://api.firecrawl.dev/v1/search"


def _result_to_document(item: dict, source_type: str) -> RawDocument | None:
    metadata = item.get("metadata") or {}
    url = item.get("url") or metadata.get("sourceURL") or metadata.get("url")
    raw_title = item.get("title") or metadata.get("title")
    body = (
        item.get("description")
        or item.get("markdown")
        or metadata.get("description")
        or ""
    )
    # A result with only a URL (no title and no body) carries no usable signal.
    if not raw_title and not body:
        return None
    title = raw_title or url
    text = f"{title}. {body}".strip()
    published = (
        metadata.get("publishedTime")
        or metadata.get("published_time")
        or metadata.get("date")
    )
    return RawDocument(
        external_id=url,
        title=title,
        text=text[:4000],
        url=url,
        published_at=parse_date(published),
        language=metadata.get("language"),
        source_name="Firecrawl",
        source_type=source_type,
    )


class FirecrawlConnector:
    """Fetch web/news results from Firecrawl's search API. Requires an API key."""

    source_name = "Firecrawl"
    source_type = "news"

    def __init__(
        self,
        api_key: str,
        client: httpx.Client | None = None,
        source_type: str = "news",
    ) -> None:
        if not api_key:
            raise ValueError("FirecrawlConnector requires an API key.")
        self._api_key = api_key
        self.source_type = source_type
        self._client = client or httpx.Client(timeout=60.0)

    def fetch(self, query: str, limit: int = 50) -> list[RawDocument]:
        resp = self._client.post(
            FIRECRAWL_SEARCH_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"query": query, "limit": min(limit, 50)},
        )
        resp.raise_for_status()
        payload = resp.json()
        items = payload.get("data") or payload.get("results") or []
        docs: list[RawDocument] = []
        for item in items:
            doc = _result_to_document(item, self.source_type)
            if doc and doc.text.strip():
                docs.append(doc)
        return docs
