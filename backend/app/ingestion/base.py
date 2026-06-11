"""Common ingestion types and the connector protocol."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from pydantic import BaseModel


def parse_date(value: str | None) -> datetime | None:
    """Best-effort ISO-ish date parsing shared by all connectors (``None`` on failure).

    Handles full ISO timestamps (``2024-05-01T10:00:00Z``) and date-only strings
    (``2024-05-01``). Date-only / naive results are normalised to UTC so connectors
    keep emitting timezone-aware timestamps.
    """
    if not value:
        return None
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(str(value), "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


class RawDocument(BaseModel):
    """A source-agnostic document produced by a connector."""

    external_id: str | None = None
    title: str
    text: str
    url: str | None = None
    published_at: datetime | None = None
    language: str | None = None
    region: str | None = None
    country: str | None = None
    source_name: str
    source_type: str = "science"


def doc_key(doc: RawDocument) -> str:
    """Stable identity key for de-duplication (external id, else url, else title)."""
    return (doc.external_id or doc.url or doc.title or "").strip().lower()


def dedupe(docs: list[RawDocument]) -> list[RawDocument]:
    """Drop documents sharing a :func:`doc_key`, keeping first occurrence order."""
    seen: set[str] = set()
    unique: list[RawDocument] = []
    for doc in docs:
        key = doc_key(doc)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(doc)
    return unique


class Connector(Protocol):
    """A source connector fetches raw documents for a query."""

    source_name: str
    source_type: str

    def fetch(self, query: str, limit: int = 50) -> list[RawDocument]:
        """Fetch up to ``limit`` documents matching ``query``."""
        ...
