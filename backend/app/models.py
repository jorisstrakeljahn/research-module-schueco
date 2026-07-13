"""Database models (SQLModel).

Entity overview::

    Source ─< Document ─< Chunk(embedding)
    Run ─< Topic ─< TopicTimepoint        (time series, §6.1)
              └─< Trend ─< TrendAssessment
                              └─< ExpertFeedback   (human-in-the-loop)

The ``region`` / ``country`` / ``language`` / ``source_type`` fields enable the
region- and source-type filtering described in the project plan (§7).
"""

from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, Float, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

from app.config import get_settings

EMBEDDING_DIM = get_settings().embedding_dim


def _utcnow() -> datetime:
    return datetime.now(UTC)


# Allowed values (kept as plain strings for simplicity / portability).
SOURCE_TYPES = (
    "science",
    "preprint",
    "news",
    "blog",
    "web",
    "rss",
    "patent",
    "social",
)
MATURITY_LEVELS = ("weak_signal", "emerging", "established", "megatrend")
RADAR_STAGES = ("act", "prepare", "watch")
PORTFOLIO_STATUSES = ("active", "review", "rejected", "dormant", "merged")
OCCURRENCE_CHANGES = (
    "new",
    "classification_changed",
    "content_changed",
    "evidence_only",
    "unchanged",
)
REVIEW_STATUSES = ("pending", "not_required", "approved", "rejected")

# The six classic PESTEL macro-environment dimensions (Theobald 2016; Keicher 2022),
# used as the classification label set (ADR-25). Schüco's Trendradar renders these as
# domain sectors (see PESTEL_SECTOR_LABELS); the canonical keys stay PESTEL for
# theoretical traceability.
PESTEL_DIMENSIONS = (
    "political",
    "economic",
    "social",
    "technological",
    "environmental",
    "legal",
)

# Schüco's parallel thematic colour taxonomy on the Trendradar (ADR-27): an overlay
# orthogonal to the PESTEL sectors.
TREND_CATEGORIES = ("climate", "technology", "digital", "markets")


class Source(SQLModel, table=True):
    __tablename__ = "source"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    source_type: str = Field(default="science", index=True)
    url: str | None = None
    region: str | None = Field(default=None, index=True)
    country: str | None = Field(default=None, index=True)
    language: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=_utcnow)

    documents: list["Document"] = Relationship(back_populates="source")


class Document(SQLModel, table=True):
    __tablename__ = "document"

    id: int | None = Field(default=None, primary_key=True)
    source_id: int | None = Field(default=None, foreign_key="source.id", index=True)
    external_id: str | None = Field(default=None, index=True)  # for de-duplication
    doi: str | None = Field(default=None, index=True, unique=True)
    canonical_url: str | None = Field(default=None, index=True, unique=True)
    content_hash: str | None = Field(default=None, index=True, unique=True)
    normalized_identity: str | None = Field(default=None, index=True, unique=True)
    duplicate_of_id: int | None = Field(default=None, foreign_key="document.id")
    near_duplicate_of_id: int | None = Field(default=None, foreign_key="document.id")
    corpus_approved: bool = Field(
        default=True,
        sa_column=Column(
            Boolean, nullable=False, server_default=text("false"), index=True
        ),
    )
    title: str
    text: str
    url: str | None = None
    published_at: datetime | None = Field(default=None, index=True)
    language: str | None = Field(default=None, index=True)
    region: str | None = Field(default=None, index=True)
    country: str | None = Field(default=None, index=True)
    raw_snapshot_ref: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)

    source: Source | None = Relationship(back_populates="documents")
    chunks: list["Chunk"] = Relationship(back_populates="document")


class Chunk(SQLModel, table=True):
    __tablename__ = "chunk"

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="document.id", index=True)
    chunk_index: int = 0
    text: str
    embedding: list[float] | None = Field(
        default=None, sa_column=Column(Vector(EMBEDDING_DIM))
    )

    document: Document | None = Relationship(back_populates="chunks")


class DocumentEmbedding(SQLModel, table=True):
    """Reusable whole-document embedding keyed by immutable content and model."""

    __tablename__ = "document_embedding"
    __table_args__ = (
        UniqueConstraint(
            "content_hash", "model_name", "model_revision", name="uq_document_embedding"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="document.id", index=True)
    content_hash: str = Field(index=True)
    model_name: str
    model_revision: str = "default"
    embedding: list[float] = Field(sa_column=Column(Vector(EMBEDDING_DIM)))
    created_at: datetime = Field(default_factory=_utcnow)


class Run(SQLModel, table=True):
    __tablename__ = "run"

    id: int | None = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=_utcnow)
    finished_at: datetime | None = None
    status: str = Field(default="running")  # running | completed | failed
    embedder: str | None = None
    topic_model: str | None = None
    describer: str | None = None
    params: dict | None = Field(default=None, sa_column=Column(JSONB))
    corpus_hash: str | None = Field(default=None, index=True)
    corpus_cutoff: datetime | None = None
    component_manifest: dict | None = Field(default=None, sa_column=Column(JSONB))
    prompt_manifest: dict | None = Field(default=None, sa_column=Column(JSONB))
    git_revision: str | None = None
    embedder_revision: str | None = None
    topic_model_revision: str | None = None
    random_seed: int = Field(
        default=42,
        sa_column=Column(Integer, nullable=False, server_default=text("42")),
    )
    classifier: str | None = None
    usage_metrics: dict | None = Field(default=None, sa_column=Column(JSONB))
    n_documents: int = 0
    n_topics: int = 0
    error: str | None = None  # populated when status == "failed"

    topics: list["Topic"] = Relationship(back_populates="run")


class RunEvent(SQLModel, table=True):
    """Append-only progress event emitted while a pipeline run is executing."""

    __tablename__ = "run_event"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True)
    phase: str = Field(index=True)
    progress: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default=text("0")),
    )
    message: str
    details: dict | None = Field(default=None, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=_utcnow)


class Topic(SQLModel, table=True):
    __tablename__ = "topic"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True)
    topic_index: int
    label: str
    keywords: list[str] | None = Field(default=None, sa_column=Column(JSONB))
    size: int = 0
    # Dominant region/country of the topic's documents, aggregated at run time so the
    # Trendradar can be filtered by region (project plan §7.3). Null when the sources
    # carry no geographic metadata.
    region: str | None = Field(default=None, index=True)
    country: str | None = Field(default=None, index=True)
    # Centroid embedding of the topic's documents; persisted so emergence (semantic
    # novelty) can be measured against the previous run's topics (ADR-19).
    centroid: list[float] | None = Field(
        default=None, sa_column=Column(Vector(EMBEDDING_DIM))
    )

    run: Run | None = Relationship(back_populates="topics")
    trend: "Trend" = Relationship(back_populates="topic")
    timepoints: list["TopicTimepoint"] = Relationship(back_populates="topic")


class TopicTimepoint(SQLModel, table=True):
    __tablename__ = "topic_timepoint"

    id: int | None = Field(default=None, primary_key=True)
    topic_id: int = Field(foreign_key="topic.id", index=True)
    period: str  # e.g. "2024-Q1"
    doc_count: int = 0
    prevalence: float = Field(
        default=0.0,
        sa_column=Column(Float, nullable=False, server_default=text("0")),
    )

    topic: Topic | None = Relationship(back_populates="timepoints")


class Trend(SQLModel, table=True):
    __tablename__ = "trend"

    id: int | None = Field(default=None, primary_key=True)
    topic_id: int = Field(foreign_key="topic.id", index=True, unique=True)
    run_id: int = Field(foreign_key="run.id", index=True)
    title: str
    summary: str = ""
    maturity: str | None = None  # one of MATURITY_LEVELS
    # Semantic novelty in [0, 1] vs. the previous run (None on the first run); the
    # emergence axis of the topic matrix (ADR-19).
    emergence: float | None = None
    evidence: list[dict] | None = Field(default=None, sa_column=Column(JSONB))

    topic: Topic | None = Relationship(back_populates="trend")
    assessment: "TrendAssessment" = Relationship(back_populates="trend")
    feedback: list["ExpertFeedback"] = Relationship(back_populates="trend")


class TrendAssessment(SQLModel, table=True):
    __tablename__ = "trend_assessment"

    id: int | None = Field(default=None, primary_key=True)
    trend_id: int = Field(foreign_key="trend.id", index=True, unique=True)
    pestel: list[str] | None = Field(default=None, sa_column=Column(JSONB))
    category: str | None = None  # one of TREND_CATEGORIES (radar colour, ADR-27)
    impact: float | None = None  # 1-10 (ADR-26)
    urgency: float | None = None  # 1-10, "Dringlichkeit"; with impact -> radar ring
    uncertainty: float | None = None  # 1-10, for the separate impact/uncertainty grid
    radar_stage: str | None = None  # one of RADAR_STAGES
    rationale: str | None = None

    trend: Trend | None = Relationship(back_populates="assessment")


class ReferenceTrend(SQLModel, table=True):
    """A manually-identified trend from the practice partner's existing process.

    Stored as the evaluation baseline: the overlap between the system's discovered
    trends and this curated list yields the precision/recall-style "strategische
    Relevanz" metric of the project plan (§11). Independent of any Run.
    """

    __tablename__ = "reference_trend"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    keywords: list[str] | None = Field(default=None, sa_column=Column(JSONB))
    pestel: list[str] | None = Field(default=None, sa_column=Column(JSONB))
    category: str | None = None
    source: str = "schueco_manual"  # provenance of the reference entry
    note: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class ExpertFeedback(SQLModel, table=True):
    __tablename__ = "expert_feedback"

    id: int | None = Field(default=None, primary_key=True)
    trend_id: int = Field(foreign_key="trend.id", index=True)
    action: str  # confirm | correct | reject
    field: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    comment: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)

    trend: Trend | None = Relationship(back_populates="feedback")


class TrendTranslation(SQLModel, table=True):
    """Cached on-demand translation of a trend (trend text is immutable per run)."""

    __tablename__ = "trend_translation"

    id: int | None = Field(default=None, primary_key=True)
    trend_id: int = Field(foreign_key="trend.id", index=True)
    language: str
    title: str
    summary: str = ""
    rationale: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class CanonicalTrend(SQLModel, table=True):
    """Stable portfolio identity; run-specific machine output remains in ``Trend``."""

    __tablename__ = "canonical_trend"

    id: str = Field(primary_key=True)
    status: str = Field(default="active", index=True)
    title: str
    summary: str = ""
    maturity: str | None = None
    pestel: list[str] | None = Field(default=None, sa_column=Column(JSONB))
    category: str | None = None
    impact: float | None = None
    urgency: float | None = None
    uncertainty: float | None = None
    radar_stage: str | None = None
    # Full bilingual text: {"de": {"title","summary","rationale"}, "en": {...}}.
    # ``title``/``summary`` above stay the curation default; the API serves the
    # requested language from here so DE and EN views are both first-class.
    translations: dict | None = Field(default=None, sa_column=Column(JSONB))
    # Manual sort position inside the newsfeed maturity column (drag & drop).
    position: float | None = Field(default=None)
    first_run_id: int | None = Field(default=None, foreign_key="run.id", index=True)
    last_run_id: int | None = Field(default=None, foreign_key="run.id", index=True)
    merged_into_id: str | None = Field(default=None, foreign_key="canonical_trend.id")
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class RunDocument(SQLModel, table=True):
    """Materialized, immutable membership of a run's cumulative corpus."""

    __tablename__ = "run_document"
    __table_args__ = (UniqueConstraint("run_id", "document_id", name="uq_run_document"),)

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True)
    document_id: int = Field(foreign_key="document.id", index=True)
    provenance: str  # new | carried_forward
    position: int
    topic_index: int | None = Field(default=None, index=True)
    is_outlier: bool = False
    membership_probability: float | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class TrendOccurrence(SQLModel, table=True):
    """One run observation, linked after its identity has been accepted."""

    __tablename__ = "trend_occurrence"

    id: int | None = Field(default=None, primary_key=True)
    canonical_trend_id: str | None = Field(
        default=None, foreign_key="canonical_trend.id", index=True
    )
    trend_id: int = Field(foreign_key="trend.id", index=True, unique=True)
    run_id: int = Field(foreign_key="run.id", index=True)
    change_type: str = Field(index=True)
    match_score: float | None = None
    match_margin: float | None = None
    changed_fields: list[str] | None = Field(default=None, sa_column=Column(JSONB))
    review_status: str = Field(
        default="not_required",
        sa_column=Column(
            String, nullable=False, server_default=text("'not_required'"), index=True
        ),
    )
    review_reasons: list[dict] | None = Field(default=None, sa_column=Column(JSONB))
    evidence_added_count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default=text("0")),
    )
    evidence_removed_count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default=text("0")),
    )
    # Deprecated compatibility projection. New code uses structured review_reasons.
    review_reason: str | None = None
    prevalence: float | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class TrendDecision(SQLModel, table=True):
    """Append-only human decision audit trail."""

    __tablename__ = "trend_decision"

    id: int | None = Field(default=None, primary_key=True)
    canonical_trend_id: str | None = Field(
        default=None, foreign_key="canonical_trend.id", index=True
    )
    occurrence_id: int | None = Field(
        default=None, foreign_key="trend_occurrence.id", index=True
    )
    action: str
    reviewer: str
    reason: str | None = None
    before_values: dict | None = Field(default=None, sa_column=Column(JSONB))
    after_values: dict | None = Field(default=None, sa_column=Column(JSONB))
    idempotency_key: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=_utcnow)


class BaselineSnapshot(SQLModel, table=True):
    __tablename__ = "baseline_snapshot"

    key: str = Field(primary_key=True)
    title: str
    source: str
    source_run_id: int | None = Field(default=None, foreign_key="run.id")
    created_at: datetime = Field(default_factory=_utcnow)


class BaselineTrend(SQLModel, table=True):
    """Immutable values exactly as accepted for a historical report snapshot."""

    __tablename__ = "baseline_trend"
    __table_args__ = (
        UniqueConstraint("snapshot_key", "position", name="uq_baseline_position"),
        UniqueConstraint("snapshot_key", "legacy_trend_id", name="uq_baseline_legacy"),
    )

    id: int | None = Field(default=None, primary_key=True)
    snapshot_key: str = Field(foreign_key="baseline_snapshot.key", index=True)
    position: int
    legacy_trend_id: int
    canonical_trend_id: str | None = Field(
        default=None, foreign_key="canonical_trend.id", index=True
    )
    title: str
    relevance: float | None = None
    novelty: str | None = None
    traceability: float | None = None
    payload: dict | None = Field(default=None, sa_column=Column(JSONB))
