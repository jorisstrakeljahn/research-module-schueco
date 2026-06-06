"""Application configuration loaded from environment / .env file."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings. Values come from environment variables or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = (
        "postgresql+psycopg://trendscout:trendscout@localhost:5433/trendscout"
    )

    # Pipeline component selection (see .env.example for options)
    embedder: str = "hashing"
    topic_model: str = "simple"
    topic_max: int = 12  # upper bound on number of topics/clusters per run
    describer: str = "template"
    classifier: str = "heuristic"  # PESTEL/impact assessment: heuristic | openai
    translator: str = "auto"  # on-demand DE/EN translation: auto | openai | none
    language: str = "en"  # language of LLM-generated trend text: en | de
    embedding_dim: int = 384

    # Data sources: comma-separated list of connector names (openalex, arxiv, firecrawl)
    sources: str = "openalex"

    # Deep-research crawler (focused crawling / snowball sampling, ADR-22)
    expander: str = "none"  # query expansion: none | openai
    relevance: str = "off"  # relevance gate: off | keyword | openai
    research_domain: str = "building envelope and facade technology"
    research_max_rounds: int = 2
    research_max_docs: int = 80
    research_per_query_limit: int = 20
    research_expand_terms: int = 4
    seed_terms: str = ""  # comma-separated; overrides the built-in domain seeds when set

    # External APIs
    openalex_mailto: str = ""
    openai_api_key: str = ""
    firecrawl_api_key: str = ""

    @property
    def source_list(self) -> list[str]:
        """Parsed, normalized list of enabled source connector names."""
        return [s.strip().lower() for s in self.sources.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
