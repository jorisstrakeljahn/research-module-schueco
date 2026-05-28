"""Common ingestion types and the connector protocol."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel


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


class Connector(Protocol):
    """A source connector fetches raw documents for a query."""

    source_name: str
    source_type: str

    def fetch(self, query: str, limit: int = 50) -> list[RawDocument]:
        """Fetch up to ``limit`` documents matching ``query``."""
        ...
