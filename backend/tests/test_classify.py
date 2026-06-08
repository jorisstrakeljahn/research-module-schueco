"""Tests for the offline trend classifier and radar-stage mapping."""

from __future__ import annotations

from app.models import PESTEL_DIMENSIONS, TREND_CATEGORIES
from app.pipeline.classify import (
    HeuristicClassifier,
    TrendSignal,
    get_classifier,
    radar_stage,
)


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
