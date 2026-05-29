"""Topic modeling components (pluggable).

The offline :class:`SimpleTopicModeler` clusters embeddings with K-Means and labels
each cluster via a class-based TF-IDF (c-TF-IDF), mirroring the idea behind BERTopic
(Grootendorst, 2022). :class:`BERTopicModeler` is the scientific default once the
``ml`` extra is installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np


@dataclass
class TopicInfo:
    topic_index: int
    label: str
    keywords: list[str]
    size: int


@dataclass
class TopicResult:
    labels: list[int]  # topic index per document (-1 = outlier / no topic)
    topics: list[TopicInfo] = field(default_factory=list)


class TopicModeler(Protocol):
    def fit(self, texts: list[str], embeddings: np.ndarray) -> TopicResult:
        ...


def _ctfidf_keywords(
    texts: list[str], labels: np.ndarray, topn: int = 8
) -> dict[int, list[str]]:
    """Compute the top class-based TF-IDF keywords per cluster."""
    from sklearn.feature_extraction.text import CountVectorizer

    try:
        vectorizer = CountVectorizer(stop_words="english", min_df=1)
        counts = vectorizer.fit_transform(texts)  # (n_docs, vocab)
    except ValueError:
        return {}
    vocab = np.array(vectorizer.get_feature_names_out())
    unique = sorted(set(int(x) for x in labels))

    # class term frequency: sum counts per cluster
    class_tf = np.vstack(
        [np.asarray(counts[labels == c].sum(axis=0)).ravel() for c in unique]
    ).astype(float)
    total_per_term = class_tf.sum(axis=0)  # f_t across classes
    total_per_term[total_per_term == 0] = 1.0
    avg_words = class_tf.sum() / max(len(unique), 1)
    idf = np.log(1.0 + avg_words / total_per_term)
    ctfidf = class_tf * idf

    keywords: dict[int, list[str]] = {}
    for row, cluster in enumerate(unique):
        top_idx = np.argsort(ctfidf[row])[::-1][:topn]
        keywords[cluster] = [vocab[i] for i in top_idx if ctfidf[row, i] > 0]
    return keywords


class SimpleTopicModeler:
    """Offline topic modeler: K-Means over embeddings + c-TF-IDF labels."""

    def __init__(self, n_topics: int | None = None, random_state: int = 42) -> None:
        self.n_topics = n_topics
        self.random_state = random_state

    def _choose_k(self, n_docs: int) -> int:
        if self.n_topics:
            return max(1, min(self.n_topics, n_docs))
        return max(1, min(8, n_docs // 3 or 1))

    def fit(self, texts: list[str], embeddings: np.ndarray) -> TopicResult:
        n = len(texts)
        if n == 0:
            return TopicResult(labels=[])

        k = self._choose_k(n)
        if k == 1:
            labels = np.zeros(n, dtype=int)
        else:
            from sklearn.cluster import KMeans

            labels = KMeans(
                n_clusters=k, n_init=10, random_state=self.random_state
            ).fit_predict(embeddings)

        keywords = _ctfidf_keywords(texts, labels)
        topics: list[TopicInfo] = []
        for cluster in sorted(set(int(x) for x in labels)):
            kws = keywords.get(cluster, [])
            label = ", ".join(kws[:3]) if kws else f"topic {cluster}"
            topics.append(
                TopicInfo(
                    topic_index=cluster,
                    label=label,
                    keywords=kws,
                    size=int(np.sum(labels == cluster)),
                )
            )
        return TopicResult(labels=[int(x) for x in labels], topics=topics)


class BERTopicModeler:
    """Scientific default using BERTopic (Grootendorst, 2022). Requires ``ml`` extra."""

    def __init__(self, n_topics: int | None = None) -> None:
        self.n_topics = n_topics

    def fit(self, texts: list[str], embeddings: np.ndarray) -> TopicResult:
        from bertopic import BERTopic

        model = BERTopic(nr_topics=self.n_topics, calculate_probabilities=False)
        labels, _ = model.fit_transform(texts, embeddings=embeddings)
        topics: list[TopicInfo] = []
        for topic_index in sorted(set(int(x) for x in labels)):
            words = model.get_topic(topic_index) or []
            keywords = [w for w, _ in words][:8]
            label = ", ".join(keywords[:3]) if keywords else f"topic {topic_index}"
            topics.append(
                TopicInfo(
                    topic_index=topic_index,
                    label=label,
                    keywords=keywords,
                    size=int(sum(1 for x in labels if x == topic_index)),
                )
            )
        return TopicResult(labels=[int(x) for x in labels], topics=topics)


def get_topic_modeler(name: str, n_topics: int | None = None) -> TopicModeler:
    """Factory: resolve a topic modeler by name."""
    name = name.lower()
    if name == "simple":
        return SimpleTopicModeler(n_topics=n_topics)
    if name == "bertopic":
        return BERTopicModeler(n_topics=n_topics)
    raise ValueError(f"Unknown topic model: {name!r}")
