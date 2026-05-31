"""arXiv connector.

arXiv (https://arxiv.org) exposes a free Atom-based API and requires no API key.
Preprints appear there months to years before the peer-reviewed version is indexed
in catalogues such as OpenAlex, which makes arXiv a faster (``emerging``-stage)
signal source in the multi-source strategy (ADR-20).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime

import httpx

from app.ingestion.base import RawDocument

ARXIV_API_URL = "https://export.arxiv.org/api/query"
_ATOM = {"a": "http://www.w3.org/2005/Atom"}


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # arXiv timestamps look like "2023-05-01T12:00:00Z".
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_atom(xml_text: str) -> list[RawDocument]:
    """Parse an arXiv Atom feed into :class:`RawDocument` objects."""
    root = ET.fromstring(xml_text)
    docs: list[RawDocument] = []
    for entry in root.findall("a:entry", _ATOM):
        title = (entry.findtext("a:title", default="", namespaces=_ATOM) or "").strip()
        summary = (
            entry.findtext("a:summary", default="", namespaces=_ATOM) or ""
        ).strip()
        url = (entry.findtext("a:id", default="", namespaces=_ATOM) or "").strip()
        published = entry.findtext("a:published", default=None, namespaces=_ATOM)
        if not title:
            continue
        text = f"{title}. {summary}".strip()
        docs.append(
            RawDocument(
                external_id=url or None,
                title=title,
                text=text,
                url=url or None,
                published_at=_parse_date(published),
                language="en",
                source_name="arXiv",
                source_type="preprint",
            )
        )
    return docs


class ArxivConnector:
    """Fetch preprints from the arXiv Atom API."""

    source_name = "arXiv"
    source_type = "preprint"

    def __init__(self, client: httpx.Client | None = None) -> None:
        # A descriptive User-Agent reduces arXiv throttling on rapid requests.
        self._client = client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "trendscout/0.1 (research module; mailto:research@example.org)"},
        )

    def _params(self, query: str, limit: int) -> dict[str, str]:
        return {
            "search_query": f"all:{query}",
            "start": "0",
            "max_results": str(min(limit, 100)),
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

    def fetch(self, query: str, limit: int = 50) -> list[RawDocument]:
        resp = self._client.get(ARXIV_API_URL, params=self._params(query, limit))
        resp.raise_for_status()
        return parse_atom(resp.text)
