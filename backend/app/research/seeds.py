"""Domain seed terms for the deep-research crawler.

Seeds are the starting frontier of the focused crawl. The defaults are tailored to
Schüco's building-envelope domain; they can be overridden via the ``SEED_TERMS``
setting and are augmented at runtime by terms learned from expert feedback (ADR-02).
"""

from __future__ import annotations

from app.config import Settings, get_settings

# Schüco's ten strategic fields (provided by Group Innovation, 04.05.2026) translated
# into search seeds. These are the official focus areas of the practice partner and so
# form the most relevant starting frontier for the focused crawl (ADR-22).
DEFAULT_SEEDS: list[str] = [
    "circularity and future building materials",
    "climate resilient construction",
    "regenerative and energy efficient buildings",
    "building renovation and industrial retrofit",
    "construction industrialization and on-site automation",
    "AI and autonomous planning in construction",
    "digital markets and servitization building industry",
    "construction workforce skills enablement",
    "facade sensors and building skin",
    "decarbonization of buildings",
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
