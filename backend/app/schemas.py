"""API response/request schemas (read models)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class RunOut(BaseModel):
    id: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    n_documents: int
    n_topics: int
    embedder: str | None
    topic_model: str | None
    describer: str | None


class TimepointOut(BaseModel):
    period: str
    doc_count: int


class TrendOut(BaseModel):
    id: int
    run_id: int
    title: str
    summary: str
    maturity: str | None
    emergence: float | None = None
    keywords: list[str]
    size: int
    region: str | None = None
    country: str | None = None
    pestel: list[str] | None = None
    category: str | None = None
    impact: float | None = None
    urgency: float | None = None
    uncertainty: float | None = None
    radar_stage: str | None = None


class TrendDetailOut(TrendOut):
    rationale: str | None = None
    evidence: list[dict] = []
    timeseries: list[TimepointOut] = []


class RunRequest(BaseModel):
    keywords: list[str] = []
    query: str | None = None
    limit: int = 50
    language: str = "en"  # en | de — language of generated trend text
    mode: str = "deep_research"  # deep_research | simple


class FeedbackIn(BaseModel):
    action: str  # "confirm" | "correct" | "reject"
    field: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    comment: str | None = None


class FeedbackOut(BaseModel):
    id: int
    trend_id: int
    action: str


class TranslateIn(BaseModel):
    language: str = "en"  # target language: en | de


class TranslateOut(BaseModel):
    language: str
    title: str
    summary: str
    rationale: str | None = None


class ReferenceTrendIn(BaseModel):
    title: str
    keywords: list[str] = []
    pestel: list[str] | None = None
    category: str | None = None
    note: str | None = None


class ReferenceTrendOut(BaseModel):
    id: int
    title: str
    keywords: list[str]
    pestel: list[str] | None = None
    category: str | None = None
    source: str
    note: str | None = None


class OverlapMatch(BaseModel):
    reference_id: int
    reference_title: str
    trend_id: int
    trend_title: str
    score: float


class ReferenceSummary(BaseModel):
    id: int
    title: str


class EvaluationOut(BaseModel):
    run_id: int | None
    n_references: int
    n_trends: int
    matched_references: int
    precision: float
    recall: float
    threshold: float
    matches: list[OverlapMatch]
    missed_references: list[ReferenceSummary]
    novel_trends: list[ReferenceSummary]
