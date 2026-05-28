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
from sqlalchemy import Column
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
    n_documents: int = 0
    n_topics: int = 0

    topics: list["Topic"] = Relationship(back_populates="run")


class Topic(SQLModel, table=True):
    __tablename__ = "topic"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True)
    topic_index: int
    label: str
    keywords: list[str] | None = Field(default=None, sa_column=Column(JSONB))
    size: int = 0

    run: Run | None = Relationship(back_populates="topics")
    trend: "Trend" = Relationship(back_populates="topic")
    timepoints: list["TopicTimepoint"] = Relationship(back_populates="topic")


class TopicTimepoint(SQLModel, table=True):
    __tablename__ = "topic_timepoint"

    id: int | None = Field(default=None, primary_key=True)
    topic_id: int = Field(foreign_key="topic.id", index=True)
    period: str  # e.g. "2024-Q1"
    doc_count: int = 0

    topic: Topic | None = Relationship(back_populates="timepoints")


class Trend(SQLModel, table=True):
    __tablename__ = "trend"

    id: int | None = Field(default=None, primary_key=True)
    topic_id: int = Field(foreign_key="topic.id", index=True, unique=True)
    run_id: int = Field(foreign_key="run.id", index=True)
    title: str
    summary: str = ""
    maturity: str | None = None  # one of MATURITY_LEVELS
    evidence: list[dict] | None = Field(default=None, sa_column=Column(JSONB))

    topic: Topic | None = Relationship(back_populates="trend")
    assessment: "TrendAssessment" = Relationship(back_populates="trend")
    feedback: list["ExpertFeedback"] = Relationship(back_populates="trend")


class TrendAssessment(SQLModel, table=True):
    __tablename__ = "trend_assessment"

    id: int | None = Field(default=None, primary_key=True)
    trend_id: int = Field(foreign_key="trend.id", index=True, unique=True)
    pestel: list[str] | None = Field(default=None, sa_column=Column(JSONB))
    impact: float | None = None
    uncertainty: float | None = None
    radar_stage: str | None = None  # one of RADAR_STAGES
    rationale: str | None = None

    trend: Trend | None = Relationship(back_populates="assessment")


class ExpertFeedback(SQLModel, table=True):
    __tablename__ = "expert_feedback"

    id: int | None = Field(default=None, primary_key=True)
    trend_id: int = Field(foreign_key="trend.id", index=True)
    action: str  # confirm | correct
    field: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    comment: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)

    trend: Trend | None = Relationship(back_populates="feedback")
