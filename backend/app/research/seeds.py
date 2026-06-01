"""Domain seed terms for the deep-research crawler.

Seeds are the starting frontier of the focused crawl. The defaults are tailored to
Schüco's building-envelope domain; they can be overridden via the ``SEED_TERMS``
setting and are augmented at runtime by terms learned from expert feedback (ADR-02).
"""

from __future__ import annotations

from app.config import Settings, get_settings

DEFAULT_SEEDS: list[str] = [
    "adaptive facade",
    "building envelope energy efficiency",
    "building integrated photovoltaics",
    "electrochromic smart glass glazing",
    "facade automation and sensors",
    "prefabricated facade modules",
    "sustainable building materials envelope",
    "thermal insulation high performance",
]


def default_seeds() -> list[str]:
    return list(DEFAULT_SEEDS)


def load_seeds(settings: Settings | None = None) -> list[str]:
    """Return seed terms: explicit ``SEED_TERMS`` if set, otherwise the defaults."""
    settings = settings or get_settings()
    explicit = [s.strip() for s in settings.seed_terms.split(",") if s.strip()]
    seeds = explicit or default_seeds()
    # Deduplicate while preserving order.
    return list(dict.fromkeys(seeds))


def merge_seeds(*groups: list[str]) -> list[str]:
    """Merge several seed lists, deduplicating case-insensitively, order-preserving."""
    seen: set[str] = set()
    merged: list[str] = []
    for group in groups:
        for term in group:
            term = (term or "").strip()
            if not term:
                continue
            low = term.lower()
            if low in seen:
                continue
            seen.add(low)
            merged.append(term)
    return merged
