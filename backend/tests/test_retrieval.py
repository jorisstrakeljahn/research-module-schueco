"""Tests for the offline RAG retrieval components."""

from __future__ import annotations

import numpy as np

from app.pipeline.retrieval import InMemoryRetriever, topic_centroid


def test_topic_centroid_is_mean_of_cluster_and_normalized():
    embeddings = np.array(
        [[1.0, 0.0], [3.0, 0.0], [0.0, 5.0]], dtype=np.float32
    )
    labels = [0, 0, 1]
    centroid = topic_centroid(embeddings, labels, 0)
    # mean of (1,0) and (3,0) is (2,0); normalized -> (1,0)
    assert np.allclose(centroid, [1.0, 0.0])
    assert np.isclose(np.linalg.norm(centroid), 1.0)


def test_topic_centroid_missing_cluster_is_zero_vector():
    embeddings = np.array([[1.0, 0.0]], dtype=np.float32)
    centroid = topic_centroid(embeddings, [0], topic_index=9)
    assert centroid.shape == (2,)
    assert np.allclose(centroid, 0.0)


def test_in_memory_retriever_returns_nearest_first():
    docs = [
        {"title": "facade", "url": "u0", "text": "t0"},
        {"title": "solar", "url": "u1", "text": "t1"},
        {"title": "facade-2", "url": "u2", "text": "t2"},
    ]
    embeddings = np.array(
        [[1.0, 0.0], [0.0, 1.0], [0.9, 0.1]], dtype=np.float32
    )
    retriever = InMemoryRetriever(docs, embeddings)
    hits = retriever.retrieve(np.array([1.0, 0.0], dtype=np.float32), k=2)
    assert [h["title"] for h in hits] == ["facade", "facade-2"]
    assert hits[0]["score"] >= hits[1]["score"]


def test_in_memory_retriever_empty_is_safe():
    assert InMemoryRetriever([], np.zeros((0, 2))).retrieve(np.zeros(2)) == []
