"""Text embedding components (pluggable)."""

from __future__ import annotations

from typing import Protocol

import numpy as np


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
        self, dim: int = 384, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"
    ) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        self.dim = self._model.get_sentence_embedding_dimension()

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.asarray(
            self._model.encode(texts, normalize_embeddings=True), dtype=np.float32
        )


class OpenAIEmbedder:
    """Embeddings via the OpenAI API. Requires the ``llm`` extra and an API key."""

    def __init__(self, dim: int = 1536, model_name: str = "text-embedding-3-small") -> None:
        from openai import OpenAI

        from app.config import get_settings

        self._client = OpenAI(api_key=get_settings().openai_api_key)
        self._model_name = model_name
        self.dim = dim

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        resp = self._client.embeddings.create(model=self._model_name, input=texts)
        return np.asarray([d.embedding for d in resp.data], dtype=np.float32)


def get_embedder(name: str, dim: int) -> Embedder:
    """Factory: resolve an embedder by name."""
    name = name.lower()
    if name == "hashing":
        return HashingEmbedder(dim=dim)
    if name == "sentence_transformers":
        return SentenceTransformerEmbedder(dim=dim)
    if name == "openai":
        return OpenAIEmbedder(dim=dim)
    raise ValueError(f"Unknown embedder: {name!r}")
