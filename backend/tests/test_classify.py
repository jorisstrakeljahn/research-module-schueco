"""Tests for the offline trend classifier and radar-stage mapping."""

from __future__ import annotations

from types import SimpleNamespace

from app.models import PESTEL_DIMENSIONS, TREND_CATEGORIES
from app.pipeline.classify import (
    HeuristicClassifier,
    OpenAIClassifier,
    TrendSignal,
    get_classifier,
    radar_stage,
)


def _stub_client(content: str) -> SimpleNamespace:
    """A minimal stand-in for the OpenAI client returning a fixed JSON payload."""

    def create(**_: object) -> SimpleNamespace:
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    return SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )


def _openai_classifier(content: str) -> OpenAIClassifier:
    clf = OpenAIClassifier.__new__(OpenAIClassifier)
    clf._client = _stub_client(content)
    clf._model_name = "stub"
    clf._fallback = HeuristicClassifier()
    return clf


def test_radar_stage_thresholds():
    assert radar_stage(impact=9, urgency=8) == "act"
    assert radar_stage(impact=6, urgency=3) == "prepare"
    assert radar_stage(impact=3, urgency=7) == "prepare"
    assert radar_stage(impact=2, urgency=2) == "watch"


def test_heuristic_classifier_picks_environmental_climate():
    sig = TrendSignal(
        keywords=["decarbonization", "carbon", "circular", "energy"],
        title="Circularity and embodied carbon in facades",
        maturity="established",
        size=12,
        n_sources=3,
        timepoints={"2022-Q1": 2, "2023-Q1": 6},
    )
    result = HeuristicClassifier().classify(sig)
    assert "environmental" in result.pestel
    assert result.category == "climate"
    assert all(p in PESTEL_DIMENSIONS for p in result.pestel)
    assert result.category in TREND_CATEGORIES
    assert 1.0 <= result.impact <= 10.0
    assert 1.0 <= result.urgency <= 10.0
    assert 1.0 <= result.uncertainty <= 10.0


def test_heuristic_classifier_digital_ai():
    sig = TrendSignal(
        keywords=["ai", "autonomous", "software", "automation"],
        title="AI and autonomous planning",
        maturity="emerging",
        size=5,
    )
    result = HeuristicClassifier().classify(sig)
    assert result.category == "digital"
    assert "technological" in result.pestel


def test_heuristic_classifier_uses_evidence_for_broader_pestel_coverage():
    result = HeuristicClassifier().classify(
        TrendSignal(
            keywords=["facade"],
            title="Adaptive renovation systems",
            evidence=[
                {"title": "EU policy incentives and public funding"},
                {"title": "Market investment and workforce skills"},
                {"title": "EPBD regulation and compliance standards"},
            ],
        )
    )
    assert 1 <= len(result.pestel) <= 3
    assert "political" in result.pestel
    assert {"economic", "social", "legal"} & set(result.pestel)


def test_novel_low_source_trend_is_more_uncertain():
    common = dict(keywords=["facade"], title="Facade", maturity="emerging", size=4)
    certain = HeuristicClassifier().classify(
        TrendSignal(**common, n_sources=5, emergence=0.0)
    )
    uncertain = HeuristicClassifier().classify(
        TrendSignal(**common, n_sources=1, emergence=0.9)
    )
    assert uncertain.uncertainty > certain.uncertainty


def test_classifier_factory():
    assert isinstance(get_classifier("heuristic"), HeuristicClassifier)


def test_openai_classifier_falls_back_on_non_numeric_scores():
    """Non-numeric LLM scores must degrade to the heuristic, not crash the run."""
    sig = TrendSignal(
        keywords=["ai", "automation"], title="AI planning", maturity="emerging", size=5
    )
    clf = _openai_classifier(
        '{"impact": "high", "urgency": "soon", "uncertainty": "low",'
        ' "category": "digital", "pestel": ["technological"]}'
    )
    result = clf.classify(sig)
    expected = HeuristicClassifier().classify(sig)

    assert result.impact == expected.impact
    assert result.urgency == expected.urgency
    assert result.uncertainty == expected.uncertainty
    assert all(p in PESTEL_DIMENSIONS for p in result.pestel)


def test_openai_classifier_ignores_string_pestel():
    """A bare string for ``pestel`` must not be iterated character by character."""
    sig = TrendSignal(
        keywords=["ai", "automation"], title="AI planning", maturity="emerging", size=5
    )
    clf = _openai_classifier(
        '{"impact": 7, "urgency": 6, "uncertainty": 4,'
        ' "category": "digital", "pestel": "technological"}'
    )
    result = clf.classify(sig)

    assert result.pestel
    assert all(p in PESTEL_DIMENSIONS for p in result.pestel)
