"""Per-request search planning without mutating global application settings."""

from __future__ import annotations

REGION_CONTEXT: dict[str, str] = {
    "global": "",
    "europe": "Europe European Union",
    "dach": "Germany Austria Switzerland DACH",
    "north_america": "North America United States Canada",
    "asia_pacific": "Asia Pacific APAC",
    "china": "China Chinese market",
}

PESTEL_LENSES: tuple[str, ...] = (
    "policy public funding geopolitics",
    "market costs investment demand supply chain",
    "users health workforce demographics society",
    "technology innovation automation digitalization",
    "climate emissions energy circularity resilience",
    "regulation standards compliance certification law",
)


def contextual_query(query: str, region: str) -> str:
    context = REGION_CONTEXT.get(region, "")
    return f"{query} {context}".strip()


def plan_deep_research_seeds(
    *,
    query: str,
    keywords: list[str],
    region: str,
    holistic_pestel: bool,
) -> list[str]:
    """Create a bounded query frontier with PESTEL coverage handled server-side."""
    focused = contextual_query(query, region)
    seeds = [focused, *keywords]
    if holistic_pestel:
        seeds.extend(f"{focused} {lens}" for lens in PESTEL_LENSES)
    return list(dict.fromkeys(seed.strip() for seed in seeds if seed.strip()))
