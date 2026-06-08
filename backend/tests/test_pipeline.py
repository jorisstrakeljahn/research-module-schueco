"""Tests for the offline pipeline components."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np

from app.pipeline.describe import TemplateDescriber
from app.pipeline.embeddings import HashingEmbedder, get_embedder
from app.pipeline.timeseries import (
    build_topic_timepoints,
    classify_maturity,
    to_period,
)
from app.pipeline.topics import SimpleTopicModeler, get_topic_modeler

# Two lexically distinct groups so the (non-semantic) HashingEmbedder can separate
# them. Real semantic separation is the job of the SentenceTransformerEmbedder.
FACADE = [
    "thermal insulation envelope retrofit efficiency",
    "insulated envelope retrofit reduces heating",
    "envelope insulation thermal retrofit performance",
]
SOLAR = [
    "digital twin simulation modeling workflow",
    "simulation digital twin data modeling",
    "modeling workflow digital twin simulation",
]


def test_hashing_embedder_shape_and_determinism():
    emb = HashingEmbedder(dim=128)
    a = emb.embed(FACADE)
    b = emb.embed(FACADE)
    assert a.shape == (3, 128)
    assert np.allclose(a, b)
    assert emb.embed([]).shape == (0, 128)


def test_embedder_factory():
    assert isinstance(get_embedder("hashing", 64), HashingEmbedder)


def test_simple_topic_modeler_separates_clusters():
    texts = FACADE + SOLAR
    embeddings = HashingEmbedder(dim=256).embed(texts)
    result = SimpleTopicModeler(n_topics=2).fit(texts, embeddings)

    assert len(result.labels) == len(texts)
    assert len(result.topics) == 2
    # The two themes should land in different clusters.
    facade_labels = set(result.labels[:3])
    solar_labels = set(result.labels[3:])
    assert facade_labels != solar_labels
    # Each topic should have meaningful keywords.
    assert all(t.keywords for t in result.topics)


def test_topic_modeler_factory():
    assert isinstance(get_topic_modeler("simple"), SimpleTopicModeler)


def test_to_period():
    assert to_period(datetime(2024, 1, 15, tzinfo=UTC)) == "2024-Q1"
    assert to_period(datetime(2024, 12, 1, tzinfo=UTC)) == "2024-Q4"


def test_build_topic_timepoints_buckets_by_quarter():
    dates = [
        datetime(2023, 1, 1, tzinfo=UTC),
        datetime(2023, 2, 1, tzinfo=UTC),
        datetime(2024, 4, 1, tzinfo=UTC),
        None,
    ]
    labels = [0, 0, 1, 0]
    tp = build_topic_timepoints(dates, labels)
    assert tp[0]["2023-Q1"] == 2
    assert tp[1]["2024-Q2"] == 1
    assert "2024-Q2" not in tp[0]


def test_classify_maturity_levels():
    assert classify_maturity({}) == "weak_signal"
    assert classify_maturity({"2024-Q1": 2}) == "weak_signal"
    # strong recent growth -> emerging
    assert (
        classify_maturity({"2022-Q1": 1, "2022-Q2": 2, "2023-Q1": 8, "2023-Q2": 10})
        == "emerging"
    )
    # sustained high volume over many quarters -> megatrend
    big = {f"20{y}-Q{q}": 5 for y in range(20, 24) for q in range(1, 5)}
    assert classify_maturity(big) == "megatrend"


def test_classify_maturity_emergence_axis():
    # A stable, voluminous-but-flat topic reads as "established"...
    stable = {"2022-Q1": 5, "2022-Q2": 5, "2023-Q1": 5, "2023-Q2": 5}
    assert classify_maturity(stable) == "established"
    # ...but if it is semantically novel vs. the previous run, it is "emerging".
    assert classify_maturity(stable, emergence=0.8) == "emerging"
    # Low novelty leaves the base level untouched.
    assert classify_maturity(stable, emergence=0.1) == "established"


def test_template_describer_is_grounded():
    rep = [
        {"title": "Adaptive facade systems", "url": "http://x/1", "text": "..."},
        {"title": "Dynamic facades", "url": "http://x/2", "text": "..."},
    ]
    desc = TemplateDescriber().describe(["facade", "adaptive", "envelope"], rep)
    assert "Facade" in desc.title
    assert "facade" in desc.summary
    assert len(desc.evidence) == 2
    assert desc.evidence[0]["url"] == "http://x/1"
