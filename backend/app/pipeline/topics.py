"""Topic modeling components (pluggable).

The offline :class:`SimpleTopicModeler` clusters embeddings with K-Means and labels
each cluster via a class-based TF-IDF (c-TF-IDF), mirroring the idea behind BERTopic
(Grootendorst, 2022). :class:`BERTopicModeler` is the scientific default once the
``ml`` extra is installed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)


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
    probabilities: list[float | None] = field(default_factory=list)


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

    def __init__(
        self,
        n_topics: int | None = None,
        max_topics: int = 12,
        random_state: int = 42,
    ) -> None:
        self.n_topics = n_topics
        self.max_topics = max(1, max_topics)
        self.random_state = random_state

    def _choose_k(self, n_docs: int) -> int:
        # An exact count overrides; otherwise target ~10 docs per topic so that larger
        # corpora yield more (and finer) clusters - the granularity needed for niche
        # weak signals and a dominant megatrend cluster - capped at ``max_topics``.
        if self.n_topics:
            return max(1, min(self.n_topics, n_docs))
        return max(1, min(self.max_topics, n_docs // 10 or 1))

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
        return TopicResult(
            labels=[int(x) for x in labels],
            topics=topics,
            probabilities=[1.0] * n,
        )


class BERTopicModeler:
    """Scientific default using BERTopic (Grootendorst, 2022). Requires ``ml`` extra."""

    def __init__(
        self,
        n_topics: int | None = None,
        *,
        max_topics: int = 12,
        random_state: int = 42,
        min_cluster_size: int = 8,
    ) -> None:
        self.n_topics = n_topics
        self.max_topics = max_topics
        self.random_state = random_state
        self.min_cluster_size = min_cluster_size

    def fit(self, texts: list[str], embeddings: np.ndarray) -> TopicResult:
        if not texts:
            return TopicResult(labels=[])
        if len(texts) < 4:
            return SimpleTopicModeler(
                n_topics=1,
                random_state=self.random_state,
            ).fit(texts, embeddings)

        try:
            from bertopic import BERTopic
            from hdbscan import HDBSCAN
            from sklearn.cluster import KMeans
            from sklearn.feature_extraction.text import CountVectorizer
            from umap import UMAP
        except ImportError:
            # The ``ml`` extra is not installed: degrade to the offline K-Means
            # modeler instead of aborting the whole run.
            logger.warning(
                "BERTopic unavailable (ml extra not installed); "
                "falling back to SimpleTopicModeler"
            )
            return SimpleTopicModeler(
                n_topics=self.n_topics,
                max_topics=self.max_topics,
                random_state=self.random_state,
            ).fit(texts, embeddings)

        def make_model(cluster_model) -> BERTopic:
            # nr_topics is a HARD cap: BERTopic merges the discovered clusters down
            # to at most this many topics, so a run never floods the review queue.
            return BERTopic(
                nr_topics=self.n_topics or self.max_topics,
                calculate_probabilities=False,
                umap_model=UMAP(
                    n_neighbors=min(15, max(2, len(texts) - 1)),
                    n_components=5,
                    min_dist=0.0,
                    metric="cosine",
                    random_state=self.random_state,
                    n_jobs=1,
                ),
                hdbscan_model=cluster_model,
                vectorizer_model=CountVectorizer(
                    ngram_range=(1, 2),
                    min_df=1,
                    stop_words="english",
                    lowercase=True,
                ),
                top_n_words=8,
                verbose=False,
            )

        hdbscan_model = HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            min_samples=max(2, self.min_cluster_size // 2),
            metric="euclidean",
            cluster_selection_method="eom",
            prediction_data=True,
            core_dist_n_jobs=1,
        )
        model = make_model(hdbscan_model)
        labels, probabilities = model.fit_transform(texts, embeddings=embeddings)

        # Dense, domain-specific corpora can make HDBSCAN collapse into one or two
        # giant clusters. That is mathematically valid but unusable for a trend
        # portfolio. Keep BERTopic's UMAP + c-TF-IDF representation and retry its
        # pluggable clustering stage with deterministic K-Means only when this
        # degeneracy is detected.
        target_topics = self.n_topics or min(
            self.max_topics, max(2, round((len(texts) / 2) ** 0.5))
        )
        discovered = len({int(label) for label in labels if int(label) >= 0})
        minimum_useful = min(target_topics, max(3, target_topics // 2))
        if len(texts) >= target_topics and discovered < minimum_useful:
            model = make_model(
                KMeans(
                    n_clusters=target_topics,
                    n_init=10,
                    random_state=self.random_state,
                )
            )
            labels, probabilities = model.fit_transform(texts, embeddings=embeddings)
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
        probability_values = (
            [float(value) for value in probabilities]
            if probabilities is not None
            else [None] * len(labels)
        )
        return TopicResult(
            labels=[int(x) for x in labels],
            topics=topics,
            probabilities=probability_values,
        )


def get_topic_modeler(
    name: str,
    n_topics: int | None = None,
    max_topics: int = 12,
    *,
    random_state: int = 42,
    min_cluster_size: int = 8,
) -> TopicModeler:
    """Factory: resolve a topic modeler by name."""
    name = name.lower()
    if name == "simple":
        return SimpleTopicModeler(n_topics=n_topics, max_topics=max_topics)
    if name == "bertopic":
        return BERTopicModeler(
            n_topics=n_topics,
            max_topics=max_topics,
            random_state=random_state,
            min_cluster_size=min_cluster_size,
        )
    raise ValueError(f"Unknown topic model: {name!r}")
