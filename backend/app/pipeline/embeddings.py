"""Text embedding components (pluggable)."""

from __future__ import annotations

from typing import Protocol

import numpy as np
from sqlmodel import Session, select

from app.llm import get_openai_client
from app.models import Chunk, Document, DocumentEmbedding
from app.pipeline.deduplication import content_fingerprint


class Embedder(Protocol):
    """Turns texts into a 2-D float array of shape ``(n_texts, dim)``."""

    dim: int

    def embed(self, texts: list[str]) -> np.ndarray:
        ...


class HashingEmbedder:
    """Deterministic, offline embedder based on a hashed bag-of-words.

    Uses scikit-learn's :class:`HashingVectorizer` with L2 normalization. Requires
    no model download and no API key, which makes it ideal for tests and demos.
    It is *not* semantic - swap in :class:`SentenceTransformerEmbedder` for quality.
    """

    def __init__(self, dim: int = 384) -> None:
        from sklearn.feature_extraction.text import HashingVectorizer

        self.dim = dim
        self._vectorizer = HashingVectorizer(
            n_features=dim, alternate_sign=False, norm="l2"
        )

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        matrix = self._vectorizer.transform(texts)
        return matrix.toarray().astype(np.float32)


class SentenceTransformerEmbedder:
    """Semantic embeddings via Sentence-BERT (Reimers & Gurevych, 2019).

    Requires the ``ml`` extra (``sentence-transformers``). The default model is
    multilingual to support the China/region use case (project plan §7.3).
    """

    def __init__(
        self,
        dim: int = 384,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        model_revision: str = "f16484b452bc5449a3ad85665709a2648b51d735",
    ) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name, revision=model_revision)
        self.dim = self._model.get_sentence_embedding_dimension()
        if self.dim != dim:
            raise ValueError(
                f"SentenceTransformer dimension {self.dim} does not match configured {dim}"
            )

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.asarray(
            self._model.encode(texts, normalize_embeddings=True), dtype=np.float32
        )


class OpenAIEmbedder:
    """Embeddings via the OpenAI API. Requires the ``llm`` extra and an API key."""

    def __init__(self, dim: int = 1536, model_name: str = "text-embedding-3-small") -> None:
        self._client = get_openai_client()
        self._model_name = model_name
        self.dim = dim

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        # text-embedding-3-* honor the `dimensions` parameter; without it the model
        # always returns 1536 dims, which then collides with the vector(EMBEDDING_DIM)
        # column on insert.
        resp = self._client.embeddings.create(
            model=self._model_name, input=texts, dimensions=self.dim
        )
        return np.asarray([d.embedding for d in resp.data], dtype=np.float32)


def get_embedder(
    name: str,
    dim: int,
    *,
    model_name: str | None = None,
    model_revision: str | None = None,
) -> Embedder:
    """Factory: resolve an embedder by name."""
    name = name.lower()
    if name == "hashing":
        return HashingEmbedder(dim=dim)
    if name == "sentence_transformers":
        kwargs = {}
        if model_name:
            kwargs["model_name"] = model_name
        if model_revision:
            kwargs["model_revision"] = model_revision
        return SentenceTransformerEmbedder(dim=dim, **kwargs)
    if name == "openai":
        return OpenAIEmbedder(dim=dim)
    raise ValueError(f"Unknown embedder: {name!r}")


def embed_documents_cached(
    session: Session,
    documents: list[Document],
    *,
    embedder: Embedder,
    model_name: str,
    model_revision: str,
) -> np.ndarray:
    """Reuse embeddings by content hash/model/revision and preserve input ordering."""
    vectors: dict[int, np.ndarray] = {}
    missing: list[Document] = []
    for document in documents:
        fingerprint = document.content_hash or content_fingerprint(
            document.title, document.text
        )
        if not document.content_hash:
            document.content_hash = fingerprint
            session.add(document)
        cached = session.exec(
            select(DocumentEmbedding).where(
                DocumentEmbedding.content_hash == fingerprint,
                DocumentEmbedding.model_name == model_name,
                DocumentEmbedding.model_revision == model_revision,
            )
        ).first()
        if cached:
            vectors[document.id] = np.asarray(cached.embedding, dtype=np.float32)
        else:
            missing.append(document)

    if missing:
        created = embedder.embed([document.text for document in missing])
        for document, vector in zip(missing, created, strict=True):
            fingerprint = document.content_hash or content_fingerprint(
                document.title, document.text
            )
            session.add(
                DocumentEmbedding(
                    document_id=document.id,
                    content_hash=fingerprint,
                    model_name=model_name,
                    model_revision=model_revision,
                    embedding=vector.tolist(),
                )
            )
            vectors[document.id] = np.asarray(vector, dtype=np.float32)

    # Chunk remains the compatibility/retrieval store; only create it once.
    for document in documents:
        chunk = session.exec(
            select(Chunk).where(Chunk.document_id == document.id, Chunk.chunk_index == 0)
        ).first()
        if not chunk:
            session.add(
                Chunk(
                    document_id=document.id,
                    chunk_index=0,
                    text=document.text,
                    embedding=vectors[document.id].tolist(),
                )
            )
    session.flush()
    if not documents:
        return np.zeros((0, embedder.dim), dtype=np.float32)
    return np.vstack([vectors[document.id] for document in documents])
