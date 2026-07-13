from __future__ import annotations

import numpy as np

from app.ingestion.base import RawDocument
from app.pipeline.deduplication import canonicalize_url, identity_for
from app.pipeline.matching import (
    MatchCandidate,
    one_to_one_match,
    sanitize_change,
    values_differ,
)
from app.pipeline.timeseries import complete_quarters, stabilize_maturity, topic_prevalence


def _candidate(
    key: str,
    vector: list[float],
    *,
    keywords: set[str] | None = None,
    documents: set[int] | None = None,
    status: str = "active",
) -> MatchCandidate:
    return MatchCandidate(
        key=key,
        centroid=np.asarray(vector),
        keywords=frozenset(keywords or set()),
        document_ids=frozenset(documents or set()),
        status=status,
    )


def test_document_identity_normalizes_doi_url_and_content():
    raw = RawDocument(
        external_id="doi:10.1000/ABC",
        title="  Adaptive   Facade ",
        text="Same  CONTENT",
        url="HTTPS://Example.COM/paper/?utm_source=x&id=2#part",
        source_name="OpenAlex",
    )
    identity = identity_for(raw, raw.source_name)
    assert identity.doi == "10.1000/abc"
    assert identity.normalized_identity == "doi:10.1000/abc"
    assert canonicalize_url(raw.url) == "https://example.com/paper?id=2"
    assert len(identity.content_hash) == 64


def test_float_noise_does_not_count_as_change():
    assert not values_differ(8.0, 8.000353813171387)
    assert values_differ(8.0, 8.4)
    assert values_differ(None, 8.0)
    assert not values_differ(["a", "b"], ["b", "a"])


def test_sanitize_change_downgrades_noise_only_diffs():
    before = {"urgency": 8.0, "uncertainty": 5.0, "summary": "old text"}
    # Pure float drift collapses to unchanged (or evidence_only with new docs).
    after_noise = {"urgency": 8.0004, "uncertainty": 5.0005, "summary": "old text"}
    assert sanitize_change(
        "classification_changed",
        ["urgency", "uncertainty"],
        before,
        after_noise,
        evidence_changed=False,
    ) == ("unchanged", [])
    assert sanitize_change(
        "classification_changed",
        ["urgency", "uncertainty"],
        before,
        after_noise,
        evidence_changed=True,
    ) == ("evidence_only", [])
    # A real summary change survives, but is content only.
    after_summary = dict(after_noise, summary="new text")
    assert sanitize_change(
        "classification_changed",
        ["summary", "urgency"],
        before,
        after_summary,
        evidence_changed=False,
    ) == ("content_changed", ["summary"])
    # A material score jump stays a reclassification.
    after_material = dict(before, urgency=10.0)
    assert sanitize_change(
        "classification_changed",
        ["urgency"],
        before,
        after_material,
        evidence_changed=False,
    ) == ("classification_changed", ["urgency"])


def test_global_matching_is_one_to_one_and_flags_ambiguity():
    current = [
        _candidate("a", [1, 0], keywords={"solar"}, documents={1, 2}),
        _candidate("b", [0, 1], keywords={"circular"}, documents={3, 4}),
    ]
    canonical = [
        _candidate("x", [1, 0], keywords={"solar"}, documents={1, 2}),
        _candidate("y", [0, 1], keywords={"circular"}, documents={3, 4}),
    ]
    matches = one_to_one_match(current, canonical)
    assert {(match.current_key, match.canonical_key) for match in matches} == {
        ("a", "x"),
        ("b", "y"),
    }
    assert all(match.review_reason is None for match in matches)


def test_split_candidate_is_reviewed_not_silently_merged():
    current = [_candidate("a", [1, 0]), _candidate("b", [0.99, 0.01])]
    canonical = [_candidate("x", [1, 0])]
    matches = one_to_one_match(current, canonical, review_threshold=0.4)
    assert len(matches) == 2
    assert {match.review_reason for match in matches} == {None, "split_candidate"}


def test_strong_match_is_not_reviewed_only_because_alternative_passes_threshold():
    current = [_candidate("a", [1, 0])]
    canonical = [
        _candidate("exact", [1, 0]),
        _candidate("broad", [0.7, 0.7]),
    ]

    match = one_to_one_match(current, canonical)[0]

    assert match.canonical_key == "exact"
    assert match.margin > 0.08
    assert match.review_reason is None


def test_quarter_completion_prevalence_and_maturity_hysteresis():
    completed = complete_quarters({"2024-Q1": 2, "2024-Q3": 1})
    assert completed == {"2024-Q1": 2, "2024-Q2": 0, "2024-Q3": 1}
    assert topic_prevalence(completed, {"2024-Q1": 4, "2024-Q3": 2}) == {
        "2024-Q1": 0.5,
        "2024-Q2": 0.0,
        "2024-Q3": 0.5,
    }
    assert stabilize_maturity("weak_signal", "megatrend", evidence_count=3) == "emerging"


def test_quarter_completion_limits_historical_outlier_window():
    completed = complete_quarters(
        {"1977-Q1": 1, "2024-Q4": 2, "2025-Q2": 3},
        max_periods=4,
    )
    assert completed == {
        "2024-Q3": 0,
        "2024-Q4": 2,
        "2025-Q1": 0,
        "2025-Q2": 3,
    }
