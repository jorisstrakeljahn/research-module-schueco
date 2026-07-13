"""API response/request schemas (read models)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


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
    params: dict[str, Any] | None = None
    error: str | None = None
    change_counts: dict[str, int] = Field(default_factory=dict)
    review_counts: dict[str, int] = Field(default_factory=dict)


class RunProgressEventOut(BaseModel):
    id: int
    phase: str
    progress: int
    message: str
    details: dict[str, Any] | None = None
    created_at: datetime


class RunProgressOut(BaseModel):
    run_id: int
    status: str
    phase: str
    progress: int
    message: str
    n_documents: int
    n_topics: int
    error: str | None = None
    events: list[RunProgressEventOut] = Field(default_factory=list)


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
    evidence: list[dict] = Field(default_factory=list)
    timeseries: list[TimepointOut] = Field(default_factory=list)


PortfolioStatus = Literal["active", "review", "rejected", "dormant", "merged"]
RunDiffKind = Literal[
    "new",
    "classification_changed",
    "content_changed",
    "evidence_only",
    "unchanged",
]
ReviewStatus = Literal["pending", "not_required", "approved", "rejected"]
DecisionAction = Literal["confirm", "correct", "reject", "restore", "link", "create", "merge"]


class PortfolioTrendOut(TrendOut):
    id: str
    status: PortfolioStatus
    first_run_id: int | None = None
    last_run_id: int | None = None
    merged_into_id: str | None = None
    occurrence_count: int = 0
    updated_at: datetime | None = None


class TrendEvidenceOut(BaseModel):
    title: str
    url: str | None = None
    source: str | None = None
    published_at: str | None = None
    run_id: int | None = None


class PortfolioTrendDetailOut(PortfolioTrendOut):
    rationale: str | None = None
    evidence: list[TrendEvidenceOut] = Field(default_factory=list)
    timeseries: list[TimepointOut] = Field(default_factory=list)


class PestelDimensionAnalysisOut(BaseModel):
    dimension: str
    relevance: float
    matched_documents: int
    total_documents: int
    signal_terms: list[str] = Field(default_factory=list)
    evidence: list[TrendEvidenceOut] = Field(default_factory=list)


class PestelAnalysisOut(BaseModel):
    trend_id: str
    run_id: int
    dimensions: list[PestelDimensionAnalysisOut]


class TrendDecisionOut(BaseModel):
    id: int
    action: DecisionAction
    reviewer: str | None
    reason: str | None = None
    created_at: datetime
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None


class TrendHistoryPointOut(BaseModel):
    run_id: int
    occurred_at: datetime | None = None
    maturity: str | None = None
    impact: float | None = None
    urgency: float | None = None
    uncertainty: float | None = None
    emergence: float | None = None
    size: int = 0
    change_type: RunDiffKind


class TrendHistoryOut(BaseModel):
    trend_id: str
    points: list[TrendHistoryPointOut]
    evidence: list[TrendEvidenceOut]
    decisions: list[TrendDecisionOut]


class RunDiffEntryOut(BaseModel):
    occurrence_id: int
    canonical_trend_id: str | None = None
    trend_id: int | None = None
    title: str
    change_type: RunDiffKind
    match_score: float | None = None
    margin: float | None = None
    changed_fields: list[str]
    review_status: ReviewStatus
    review_reasons: list[dict[str, Any]] = Field(default_factory=list)
    evidence_added_count: int = 0
    evidence_removed_count: int = 0
    prevalence: float | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None


class RunDiffOut(BaseModel):
    run_id: int
    started_at: datetime
    query: str | None = None
    counts: dict[RunDiffKind, int]
    entries: list[RunDiffEntryOut]


class SuggestedTrendOut(BaseModel):
    id: str
    title: str
    status: PortfolioStatus


class ReviewCandidateOut(BaseModel):
    id: str
    title: str
    score: float | None = None


class ReviewQueueItemOut(BaseModel):
    occurrence_id: int
    run_id: int
    canonical_trend_id: str | None = None
    title: str
    summary: str
    maturity: str | None = None
    match_score: float | None = None
    margin: float | None = None
    change_type: RunDiffKind
    review_status: ReviewStatus
    review_reasons: list[dict[str, Any]] = Field(default_factory=list)
    changed_fields: list[str] = Field(default_factory=list)
    evidence_added_count: int = 0
    evidence_removed_count: int = 0
    prevalence: float | None = None
    reason: str | None = None
    suggested_trend: SuggestedTrendOut | None = None
    candidates: list[ReviewCandidateOut] = Field(default_factory=list)


class PortfolioDecisionIn(BaseModel):
    action: Literal["confirm", "correct", "reject", "restore", "merge"]
    reviewer: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    changes: dict[str, Any] = Field(default_factory=dict)
    target_trend_id: str | int | None = None
    idempotency_key: str = Field(min_length=1)
    # UI language of manual edits; the other language is kept in sync via the
    # translator so the bilingual canonical record never drifts apart.
    language: Literal["en", "de"] = "en"


class ReviewDecisionIn(BaseModel):
    action: Literal["confirm", "correct", "reject", "link", "create", "merge"]
    reviewer: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    changes: dict[str, Any] = Field(default_factory=dict)
    canonical_trend_id: str | int | None = None
    target_trend_id: str | int | None = None
    idempotency_key: str = Field(min_length=1)
    language: Literal["en", "de"] = "en"


class RunRequest(BaseModel):
    keywords: list[str] = Field(default=[], max_length=10)
    query: str | None = Field(default=None, max_length=300)
    limit: int | None = Field(default=None, ge=1, le=200)
    language: Literal["en", "de"] = "en"
    mode: Literal["deep_research", "simple"] = "deep_research"
    depth: Literal["quick", "standard", "deep"] = "deep"
    region: Literal[
        "global", "europe", "dach", "north_america", "asia_pacific", "china"
    ] = "global"
    sources: list[
        Literal["openalex", "arxiv", "firecrawl", "firecrawl_web"]
    ] = Field(default=[], max_length=4)
    holistic_pestel: bool = True
    topic_granularity: Literal["compact", "balanced", "detailed"] = "balanced"


class SearchSourceOut(BaseModel):
    id: str
    enabled: bool
    requires_configuration: bool = False


class SearchCapabilitiesOut(BaseModel):
    sources: list[SearchSourceOut]
    default_sources: list[str]
    openai_enrichment: bool
    topic_model: str
    topic_granularities: list[str]
    max_documents: int = 200


class FeedbackIn(BaseModel):
    action: Literal["confirm", "correct", "reject"]
    field: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    comment: str | None = None


class FeedbackOut(BaseModel):
    id: int
    trend_id: int
    action: str


class TranslateIn(BaseModel):
    language: Literal["en", "de"] = "en"


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
