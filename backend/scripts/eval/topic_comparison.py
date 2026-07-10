"""Compare topic models on one materialized production-run corpus.

Runs three topic models on the identical document corpus and reports intrinsic
topic coherence and topic diversity:

  * K-Means + c-TF-IDF
  * the production ``BERTopicModeler`` configuration
  * LDA                 (Blei et al., 2003, classical baseline)

Coherence is the UMass score (Mimno et al., 2011), computed intrinsically from
document co-occurrence so no external reference corpus is required. Topic
diversity is the share of unique terms across all topic word lists (Dieng et
al., 2020). Higher is better for both.

Run after ``parse_snapshot.py``:
  uv run python scripts/eval/topic_comparison.py --run-id <id>
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import CountVectorizer

from app.config import Settings
from app.pipeline.embeddings import SentenceTransformerEmbedder
from app.pipeline.topics import BERTopicModeler

OUT_DIR = Path(__file__).resolve().parent / "_out"
TOP_N = 10


def load_corpus(path: Path) -> list[str]:
    texts = []
    with path.open(encoding="utf-8") as fh:
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


def compare(
    texts: list[str],
    *,
    model_name: str,
    model_revision: str,
    embedding_dim: int,
    seed: int,
    min_cluster_size: int,
    n_topics: int,
) -> dict:
    print(f"corpus: {len(texts)} documents")
    if len(texts) < max(10, min_cluster_size * 2):
        raise ValueError("Corpus is too small for a meaningful BERTopic comparison")
    binary, vocab = build_cooccurrence(texts)
    print(f"coherence vocabulary: {len(vocab)} terms")

    print(f"embedding with {model_name}@{model_revision} ...")
    embedder = SentenceTransformerEmbedder(
        dim=embedding_dim, model_name=model_name, model_revision=model_revision
    )
    embeddings = embedder.embed(texts)

    results = {}

    # 1) K-Means + c-TF-IDF on the exact production embeddings.
    from sklearn.cluster import KMeans

    km_labels = KMeans(
        n_clusters=n_topics, n_init=10, random_state=seed
    ).fit_predict(embeddings)
    km_topics = keywords_from_labels(texts, km_labels)
    results["kmeans_ctfidf"] = {
        "n_topics": len(km_topics),
        "n_outliers": 0,
        "coherence_umass": umass_coherence(km_topics, binary, vocab),
        "diversity": topic_diversity(km_topics),
        "topics": km_topics,
    }

    # 2) BERTopic through the same class and parameters used by production.
    bt_result = BERTopicModeler(
        random_state=seed, min_cluster_size=min_cluster_size
    ).fit(texts, embeddings)
    bt_labels = bt_result.labels
    bt_topics = [
        topic.keywords[:TOP_N]
        for topic in bt_result.topics
        if topic.topic_index >= 0 and topic.keywords
    ]
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
    lda = LatentDirichletAllocation(
        n_components=n_topics, random_state=seed, max_iter=25
    )
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

    print("\n model            topics  outliers  coherence(UMass)  diversity")
    print(" " + "-" * 64)
    for name in ("bertopic", "kmeans_ctfidf", "lda"):
        r = results[name]
        print(
            f" {name:<15} {r['n_topics']:>6} {r['n_outliers']:>9} "
            f"{r['coherence_umass']:>17.3f} {r['diversity']:>10.3f}"
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=int, required=True)
    args = parser.parse_args()
    corpus_path = OUT_DIR / f"corpus_run_{args.run_id}.jsonl"
    manifest_path = OUT_DIR / f"manifest_run_{args.run_id}.json"
    if not corpus_path.exists() or not manifest_path.exists():
        raise FileNotFoundError(
            f"Export run {args.run_id} first with scripts/eval/parse_snapshot.py"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    configuration = manifest.get("configuration") or {}
    component_manifest = configuration.get("component_manifest") or {}
    embedding_config = component_manifest.get("embedding") or {}
    topic_config = component_manifest.get("topic_config") or {}
    settings = Settings()
    if configuration.get("topic_model") != "bertopic":
        raise ValueError(
            f"Run {args.run_id} used {configuration.get('topic_model')!r}, not BERTopic"
        )
    if configuration.get("embedder") != "sentence_transformers":
        raise ValueError(
            "A production-equivalent comparison requires sentence_transformers "
            f"embeddings, got {configuration.get('embedder')!r}"
        )
    texts = load_corpus(corpus_path)
    results = compare(
        texts,
        model_name=embedding_config.get("model", settings.sentence_transformer_model),
        model_revision=configuration.get("embedder_revision")
        or settings.embedder_revision,
        embedding_dim=int(
            embedding_config.get("dimension", settings.embedding_dim)
        ),
        seed=int(configuration.get("random_seed") or settings.random_seed),
        min_cluster_size=int(
            topic_config.get("min_cluster_size", settings.bertopic_min_cluster_size)
        ),
        n_topics=int(manifest["funnel"]["topics"]),
    )
    payload = {
        "run_id": args.run_id,
        "corpus_hash": manifest.get("corpus_hash"),
        "configuration": configuration,
        "results": results,
    }
    output = OUT_DIR / f"topic_comparison_run_{args.run_id}.json"
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
