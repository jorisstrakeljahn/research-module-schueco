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
    keywords: list[str]
    size: int
    pestel: list[str] | None = None
    impact: float | None = None
    uncertainty: float | None = None
    radar_stage: str | None = None


class TrendDetailOut(TrendOut):
    evidence: list[dict] = []
    timeseries: list[TimepointOut] = []


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
