"""Regression tests for run-scoped evaluation exports."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).resolve().parents[1] / "scripts" / "eval"
sys.path.insert(0, str(EVAL_DIR))

from parse_snapshot import build_corpus, build_manifest, resolve_run_id  # noqa: E402


def _tables() -> dict[str, list[dict]]:
    return {
        "run": [
            {
                "id": "7",
                "status": "completed",
                "n_topics": "11",
            },
            {
                "id": "8",
                "status": "completed",
                "n_topics": "2",
                "corpus_hash": "abc",
                "embedder": "sentence_transformers",
                "topic_model": "bertopic",
                "random_seed": "42",
            },
        ],
        "source": [{"id": "1", "name": "openalex"}],
        "document": [
            {
                "id": "1",
                "source_id": "1",
                "title": "Legacy only",
                "text": "Must not leak into run 8",
            },
            {
                "id": "2",
                "source_id": "1",
                "title": "New",
                "text": "Run scoped",
                "content_hash": "new",
            },
            {
                "id": "3",
                "source_id": "1",
                "title": "Carried",
                "text": "Run scoped",
                "content_hash": "old",
            },
        ],
        "run_document": [
            {
                "run_id": "8",
                "document_id": "3",
                "position": "1",
                "provenance": "carried_forward",
                "topic_index": "0",
                "is_outlier": "f",
            },
            {
                "run_id": "8",
                "document_id": "2",
                "position": "0",
                "provenance": "new",
                "topic_index": "1",
                "is_outlier": "f",
            },
        ],
        "trend_occurrence": [
            {"run_id": "8", "change_type": "new"},
            {"run_id": "8", "change_type": "unchanged"},
        ],
    }


def test_legacy_run_without_membership_is_rejected() -> None:
    tables = _tables()

    with pytest.raises(ValueError, match="no materialized run_document corpus"):
        resolve_run_id(tables, 7)


def test_corpus_uses_only_ordered_run_membership() -> None:
    tables = _tables()

    assert resolve_run_id(tables, None) == 8
    corpus = build_corpus(tables, 8)

    assert [row["id"] for row in corpus] == [2, 3]
    assert [row["provenance"] for row in corpus] == ["new", "carried_forward"]

    manifest = build_manifest(tables, 8, corpus)
    assert manifest["n_documents"] == 2
    assert manifest["n_new_documents"] == 1
    assert manifest["n_carried_forward"] == 1
    assert manifest["source_distribution"] == {"openalex": 2}
    assert manifest["funnel"]["new"] == 1
    assert manifest["funnel"]["unchanged"] == 1
