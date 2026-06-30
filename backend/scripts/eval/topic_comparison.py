"""Quantitative topic-model comparison on the evaluated snapshot corpus.

Runs three topic models on the identical document corpus and reports intrinsic
topic coherence and topic diversity:

  * K-Means + c-TF-IDF  (the offline ``SimpleTopicModeler`` used in Run 7)
  * BERTopic            (Grootendorst, 2022, the scientific default)
  * LDA                 (Blei et al., 2003, classical baseline)

Coherence is the UMass score (Mimno et al., 2011), computed intrinsically from
document co-occurrence so no external reference corpus is required. Topic
diversity is the share of unique terms across all topic word lists (Dieng et
al., 2020). Higher is better for both.

Run:  uv run python scripts/eval/topic_comparison.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import CountVectorizer

OUT_DIR = Path(__file__).resolve().parent / "_out"
CORPUS = OUT_DIR / "corpus.jsonl"
N_TOPICS = 18
TOP_N = 10
EMBED_MODEL = "all-MiniLM-L6-v2"
SEED = 42


def load_corpus() -> list[str]:
    texts = []
    with CORPUS.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            title = (row.get("title") or "").strip()
            body = (row.get("text") or "").strip()[:2000]
            combined = f"{title}. {body}".strip()
            if combined:
                texts.append(combined)
    return texts


def build_cooccurrence(texts: list[str]):
    """Binary doc-term matrix + vocabulary index for UMass coherence."""
    vec = CountVectorizer(stop_words="english", min_df=5, max_df=0.5)
    counts = vec.fit_transform(texts)
    binary = (counts > 0).astype(int)
    vocab = {w: i for i, w in enumerate(vec.get_feature_names_out())}
    return binary, vocab


def umass_coherence(topics: list[list[str]], binary, vocab) -> float:
    """Mean UMass coherence over topics (Mimno et al., 2011)."""
    doc_freq = np.asarray(binary.sum(axis=0)).ravel()
    cols = {w: binary[:, i] for w, i in vocab.items()}
    scores = []
    for words in topics:
        present = [w for w in words[:TOP_N] if w in vocab]
        if len(present) < 2:
            continue
        topic_score = 0.0
        pairs = 0
        for i in range(1, len(present)):
            wi = present[i]
            for j in range(i):
                wj = present[j]
                co = int(cols[wi].multiply(cols[wj]).sum())
                topic_score += math.log((co + 1) / (doc_freq[vocab[wj]] + 1e-12))
                pairs += 1
        if pairs:
            scores.append(topic_score / pairs)
    return float(np.mean(scores)) if scores else float("nan")


def topic_diversity(topics: list[list[str]]) -> float:
    """Share of unique terms across all topic word lists (Dieng et al., 2020)."""
    all_words = [w for t in topics for w in t[:TOP_N]]
    if not all_words:
        return float("nan")
    return len(set(all_words)) / len(all_words)


def keywords_from_labels(texts, labels, topn=TOP_N) -> list[list[str]]:
    """Uniform c-TF-IDF keyword extraction given a hard document assignment."""
    vec = CountVectorizer(stop_words="english", min_df=2)
    counts = vec.fit_transform(texts)
    vocab = np.array(vec.get_feature_names_out())
    clusters = sorted(c for c in set(int(x) for x in labels) if c != -1)
    class_tf = np.vstack(
        [np.asarray(counts[np.asarray(labels) == c].sum(axis=0)).ravel() for c in clusters]
    ).astype(float)
    total = class_tf.sum(axis=0)
    total[total == 0] = 1.0
    avg = class_tf.sum() / max(len(clusters), 1)
    idf = np.log(1.0 + avg / total)
    ctfidf = class_tf * idf
    out = []
    for row in range(len(clusters)):
        idx = np.argsort(ctfidf[row])[::-1][:topn]
        out.append([vocab[i] for i in idx if ctfidf[row, i] > 0])
    return out


def main() -> None:
    texts = load_corpus()
    print(f"corpus: {len(texts)} documents")
    binary, vocab = build_cooccurrence(texts)
    print(f"coherence vocabulary: {len(vocab)} terms")

    from sentence_transformers import SentenceTransformer

    print(f"embedding with {EMBED_MODEL} ...")
    model = SentenceTransformer(EMBED_MODEL)
    embeddings = np.asarray(model.encode(texts, show_progress_bar=False))

    results = {}

    # 1) K-Means + c-TF-IDF (Run 7 modeler)
    from sklearn.cluster import KMeans

    km_labels = KMeans(n_clusters=N_TOPICS, n_init=10, random_state=SEED).fit_predict(embeddings)
    km_topics = keywords_from_labels(texts, km_labels)
    results["kmeans_ctfidf"] = {
        "n_topics": len(km_topics),
        "n_outliers": 0,
        "coherence_umass": umass_coherence(km_topics, binary, vocab),
        "diversity": topic_diversity(km_topics),
        "topics": km_topics,
    }

    # 2) BERTopic (native clustering)
    from bertopic import BERTopic

    bt = BERTopic(min_topic_size=10, calculate_probabilities=False, verbose=False)
    bt_labels, _ = bt.fit_transform(texts, embeddings=embeddings)
    bt_topics = []
    for tid in sorted(set(int(x) for x in bt_labels)):
        if tid == -1:
            continue
        words = [w for w, _ in (bt.get_topic(tid) or [])][:TOP_N]
        if words:
            bt_topics.append(words)
    results["bertopic"] = {
        "n_topics": len(bt_topics),
        "n_outliers": int(sum(1 for x in bt_labels if x == -1)),
        "coherence_umass": umass_coherence(bt_topics, binary, vocab),
        "diversity": topic_diversity(bt_topics),
        "topics": bt_topics,
    }

    # 3) LDA baseline
    from sklearn.decomposition import LatentDirichletAllocation

    lda_vec = CountVectorizer(stop_words="english", min_df=5, max_df=0.5)
    lda_counts = lda_vec.fit_transform(texts)
    lda_vocab = np.array(lda_vec.get_feature_names_out())
    lda = LatentDirichletAllocation(n_components=N_TOPICS, random_state=SEED, max_iter=25)
    lda.fit(lda_counts)
    lda_topics = [
        [lda_vocab[i] for i in comp.argsort()[::-1][:TOP_N]] for comp in lda.components_
    ]
    results["lda"] = {
        "n_topics": len(lda_topics),
        "n_outliers": 0,
        "coherence_umass": umass_coherence(lda_topics, binary, vocab),
        "diversity": topic_diversity(lda_topics),
        "topics": lda_topics,
    }

    (OUT_DIR / "topic_comparison.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("\n model            topics  outliers  coherence(UMass)  diversity")
    print(" " + "-" * 64)
    for name in ("bertopic", "kmeans_ctfidf", "lda"):
        r = results[name]
        print(
            f" {name:<15} {r['n_topics']:>6} {r['n_outliers']:>9} "
            f"{r['coherence_umass']:>17.3f} {r['diversity']:>10.3f}"
        )


if __name__ == "__main__":
    main()
