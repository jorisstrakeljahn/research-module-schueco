"""RAG retrieval over the vector store (ADR-11, ADR-14).

The trend describer must be grounded in evidence selected by *vector similarity*, not in
whichever documents happened to come first in a cluster. For each topic we build a
centroid embedding and retrieve the nearest chunks - the actual retrieval step of
retrieval-augmented generation.

Two interchangeable retrievers exist behind the same protocol:
:class:`PgVectorRetriever` runs an approximate-nearest-neighbour query against
PostgreSQL/pgvector (the scientific default, ADR-14); :class:`InMemoryRetriever` ranks
an in-memory embedding matrix and is used for offline runs and tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import numpy as np

if TYPE_CHECKING:
    from sqlmodel import Session


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    """L2-normalize each row; a 1-D input is treated as a single row."""
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def topic_centroid(
    embeddings: np.ndarray, labels: list[int], topic_index: int
) -> np.ndarray:
    """Return the L2-normalized mean embedding of the documents in ``topic_index``."""
    if embeddings.size == 0:
        return np.zeros(0, dtype=np.float32)
    mask = np.asarray(labels) == topic_index
    if not mask.any():
        return np.zeros(embeddings.shape[1], dtype=np.float32)
    centroid = embeddings[mask].mean(axis=0)
    return _l2_normalize(centroid)[0]


class Retriever(Protocol):
    def retrieve(self, query: np.ndarray, k: int = 6) -> list[dict]:
        ...


class InMemoryRetriever:
    """Rank an in-memory embedding matrix by cosine similarity to the query."""

    def __init__(self, documents: list[dict], embeddings: np.ndarray) -> None:
        self._documents = documents
        self._embeddings = _l2_normalize(embeddings) if len(documents) else embeddings

    def retrieve(self, query: np.ndarray, k: int = 6) -> list[dict]:
        if not self._documents or np.asarray(self._embeddings).size == 0:
            return []
        q = _l2_normalize(np.asarray(query))[0]
        scores = np.asarray(self._embeddings) @ q
        order = np.argsort(scores)[::-1][:k]
        results: list[dict] = []
        for i in order:
            doc = dict(self._documents[int(i)])
            doc["score"] = float(scores[int(i)])
            results.append(doc)
        return results


class PgVectorRetriever:
    """Retrieve the nearest chunks of a run via pgvector cosine distance (ADR-14).

    Restricted to ``document_ids`` (the current run's documents) so retrieval stays
    within one reproducible snapshot rather than the whole accumulated corpus.
    """

    def __init__(self, session: Session, document_ids: list[int]) -> None:
        self._session = session
        self._document_ids = [d for d in document_ids if d is not None]

    def retrieve(self, query: np.ndarray, k: int = 6) -> list[dict]:
        if not self._document_ids:
            return []
        from sqlmodel import select

        from app.models import Chunk, Document

        vector = [float(x) for x in np.asarray(query).ravel()]
        rows = self._session.exec(
            select(Chunk, Document)
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.document_id.in_(self._document_ids))
            .order_by(Chunk.embedding.cosine_distance(vector))
            .limit(k)
        ).all()
        return [{"title": doc.title, "url": doc.url, "text": doc.text} for _, doc in rows]
