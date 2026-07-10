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
    embedder: str = "sentence_transformers"
    topic_model: str = "bertopic"
    topic_max: int = 12  # upper bound on number of topics/clusters per run
    describer: str = "template"
    classifier: str = "auto"  # PESTEL/impact assessment: auto | heuristic | openai
    translator: str = "auto"  # on-demand DE/EN translation: auto | openai | none
    language: str = "en"  # language of LLM-generated trend text: en | de
    embedding_dim: int = 384
    sentence_transformer_model: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    embedder_revision: str = "f16484b452bc5449a3ad85665709a2648b51d735"
    topic_model_revision: str = "bertopic-adaptive-v2"
    random_seed: int = 42
    bertopic_min_cluster_size: int = 8
    timeseries_max_quarters: int = 24
    match_threshold: float = 0.62
    match_review_threshold: float = 0.50
    match_margin: float = 0.08
    max_llm_calls: int = 50

    # Data sources: comma-separated list of connector names (openalex, arxiv, firecrawl)
    sources: str = "openalex,arxiv,firecrawl,firecrawl_web"

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

    # Shared bearer token for state-changing routes; empty = auth disabled (local dev)
    api_token: str = ""

    @property
    def source_list(self) -> list[str]:
        """Parsed, normalized list of enabled source connector names."""
        return [s.strip().lower() for s in self.sources.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
