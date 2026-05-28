"""OpenAlex connector.

OpenAlex (https://openalex.org) is a free, open catalogue of scholarly works.
It requires no API key; supplying a contact email enables the faster "polite pool".
Abstracts are delivered as an inverted index and reconstructed here.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.config import get_settings
from app.ingestion.base import RawDocument

OPENALEX_WORKS_URL = "https://api.openalex.org/works"


def reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    """Rebuild plain abstract text from OpenAlex' ``abstract_inverted_index``."""
    if not inverted_index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted_index.items():
        for idx in idxs:
            positions.append((idx, word))
    positions.sort(key=lambda p: p[0])
    return " ".join(word for _, word in positions)


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        return None


def work_to_document(work: dict) -> RawDocument:
    """Map a single OpenAlex work object to a :class:`RawDocument`."""
    title = work.get("title") or work.get("display_name") or "(untitled)"
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
    text = f"{title}. {abstract}".strip()
    return RawDocument(
        external_id=work.get("id"),
        title=title,
        text=text,
        url=work.get("id"),
        published_at=_parse_date(work.get("publication_date")),
        language=work.get("language"),
        source_name="OpenAlex",
        source_type="science",
    )


class OpenAlexConnector:
    """Fetch scholarly works from OpenAlex."""

    source_name = "OpenAlex"
    source_type = "science"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=30.0)

    def _params(self, query: str, limit: int) -> dict[str, str]:
        # Default (relevance) sort intentionally: it spreads results across years,
        # which is what the retrospective time series (ADR-19) needs. Sorting by
        # date would only return the newest documents and collapse the series.
        params = {
            "search": query,
            "per-page": str(min(limit, 200)),
        }
        mailto = get_settings().openalex_mailto
        if mailto:
            params["mailto"] = mailto
        return params

    def fetch(self, query: str, limit: int = 50) -> list[RawDocument]:
        resp = self._client.get(OPENALEX_WORKS_URL, params=self._params(query, limit))
        resp.raise_for_status()
        results = resp.json().get("results", [])
        docs: list[RawDocument] = []
        for work in results:
            # Skip works without any usable content.
            if not (
                work.get("title")
                or work.get("display_name")
                or work.get("abstract_inverted_index")
            ):
                continue
            doc = work_to_document(work)
            if doc.text.strip():
                docs.append(doc)
        return docs
