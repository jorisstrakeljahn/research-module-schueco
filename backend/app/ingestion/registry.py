"""Connector registry: build the set of enabled source connectors from settings.

Adding a new data source means writing a connector that satisfies the
:class:`~app.ingestion.base.Connector` protocol and registering its name here.
The rest of the pipeline is source-agnostic.
"""

from __future__ import annotations

import logging

from app.config import Settings, get_settings
from app.ingestion.arxiv import ArxivConnector
from app.ingestion.base import Connector
from app.ingestion.firecrawl import FirecrawlConnector
from app.ingestion.openalex import OpenAlexConnector

logger = logging.getLogger(__name__)


def build_connectors(
    names: list[str] | None = None, settings: Settings | None = None
) -> list[Connector]:
    """Instantiate connectors for the given names (defaults to ``settings.source_list``).

    Sources that require credentials they don't have (e.g. Firecrawl without an API
    key) are skipped with a warning instead of raising, so a partial configuration
    still runs.
    """
    settings = settings or get_settings()
    names = names if names is not None else settings.source_list

    connectors: list[Connector] = []
    for name in names:
        key = name.strip().lower()
        if not key:
            continue
        if key == "openalex":
            connectors.append(OpenAlexConnector())
        elif key == "arxiv":
            connectors.append(ArxivConnector())
        elif key in ("firecrawl", "firecrawl_web"):
            # firecrawl       -> news/market signals (source_type "news")
            # firecrawl_web   -> faster, noisier web pages as weak signals ("web")
            if settings.firecrawl_api_key:
                source_type = "web" if key == "firecrawl_web" else "news"
                connectors.append(
                    FirecrawlConnector(
                        api_key=settings.firecrawl_api_key, source_type=source_type
                    )
                )
            else:
                logger.warning("Skipping %r source: FIRECRAWL_API_KEY not set.", key)
        else:
            raise ValueError(f"Unknown source connector: {name!r}")

    if not connectors:
        logger.warning("No usable connectors configured; falling back to OpenAlex.")
        connectors.append(OpenAlexConnector())
    return connectors
