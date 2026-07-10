"""End-to-end pipeline orchestration: ingest -> embed -> topics -> describe -> persist.

A single invocation corresponds to one :class:`~app.models.Run` snapshot, which makes
the process reproducible and enables run-to-run delta comparison (ADR-16/19).
"""

from __future__ import annotations

import logging
import subprocess
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version

import numpy as np
from sqlmodel import Session, select

from app.config import Settings, get_settings
from app.ingestion.base import Connector, RawDocument
from app.ingestion.openalex import OpenAlexConnector
from app.models import (
    Document,
    Run,
    RunDocument,
    Source,
    Topic,
    TopicTimepoint,
    Trend,
    TrendAssessment,
)
from app.pipeline.classify import TrendSignal, get_classifier, radar_stage
from app.pipeline.corpus import materialize_corpus
from app.pipeline.deduplication import (
    find_exact_duplicate,
    find_near_duplicate,
    identity_for,
)
from app.pipeline.describe import get_describer
from app.pipeline.embeddings import embed_documents_cached, get_embedder
from app.pipeline.emergence import compute_emergence
from app.pipeline.matching import reconcile_run
from app.pipeline.progress import ProgressCallback
from app.pipeline.retrieval import PgVectorRetriever, topic_centroid
from app.pipeline.timeseries import (
    build_topic_timepoints,
    classify_maturity,
    complete_quarters,
    topic_prevalence,
)
from app.pipeline.topics import get_topic_modeler

logger = logging.getLogger(__name__)


def _previous_topic_centroids(session: Session, current_run_id: int) -> list[np.ndarray]:
    """Topic centroids of the most recent completed run before ``current_run_id``.

    These form the semantic baseline against which the current run's topics are scored
    for emergence (novelty). Empty when this is the first run.
    """
    prev_run = session.exec(
        select(Run)
        .where(Run.status == "completed", Run.id < current_run_id)
        .order_by(Run.id.desc())
    ).first()
    if not prev_run:
        return []
    topics = session.exec(select(Topic).where(Topic.run_id == prev_run.id)).all()
    return [np.asarray(t.centroid) for t in topics if t.centroid is not None]


def _dominant_geo(docs: list[Document]) -> tuple[str | None, str | None]:
    """Most common (region, country) among a topic's documents; None when absent."""
    from collections import Counter

    regions = Counter(d.region for d in docs if d.region)
    countries = Counter(d.country for d in docs if d.country)
    region = regions.most_common(1)[0][0] if regions else None
    country = countries.most_common(1)[0][0] if countries else None
    return region, country


def _get_or_create_source(session: Session, name: str, source_type: str) -> Source:
    existing = session.exec(
        select(Source).where(Source.name == name, Source.source_type == source_type)
    ).first()
    if existing:
        return existing
    source = Source(name=name, source_type=source_type)
    session.add(source)
    session.flush()
    session.refresh(source)
    return source


def _persist_documents(
    session: Session, raw_docs: list[RawDocument]
) -> list[Document]:
    """Persist documents, grouping each under its own (name, type) source.

    Documents from a deep-research crawl can originate from several connectors, so the
    source is resolved per document rather than once for the whole batch.
    """
    docs: list[Document] = []
    source_cache: dict[tuple[str, str], Source] = {}
    for raw in raw_docs:
        cache_key = (raw.source_name, raw.source_type)
        source = source_cache.get(cache_key)
        if source is None:
            source = _get_or_create_source(session, raw.source_name, raw.source_type)
            source_cache[cache_key] = source
        identity = identity_for(raw, raw.source_name)
        if find_exact_duplicate(
            session,
            identity,
            source_id=source.id,
            external_id=raw.external_id,
        ):
            continue
        near_duplicate = find_near_duplicate(session, raw)
        doc = Document(
            source_id=source.id,
            external_id=raw.external_id,
            doi=identity.doi,
            canonical_url=identity.canonical_url,
            content_hash=identity.content_hash,
            normalized_identity=identity.normalized_identity,
            near_duplicate_of_id=near_duplicate.id if near_duplicate else None,
            corpus_approved=True,
            title=raw.title,
            text=raw.text,
            url=raw.url,
            published_at=raw.published_at,
            language=raw.language,
            region=raw.region,
            country=raw.country,
        )
        session.add(doc)
        session.flush()
        docs.append(doc)
    for doc in docs:
        session.refresh(doc)
    return docs


def _package_versions() -> dict[str, str]:
    packages = ("bertopic", "sentence-transformers", "umap-learn", "hdbscan", "numpy")
    result: dict[str, str] = {}
    for package in packages:
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "not-installed"
    return result


def _git_revision() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def create_run(
    session: Session,
    *,
    query: str,
    settings: Settings,
    limit: int,
    run_params: dict | None = None,
) -> Run:
    params = {"query": query, "limit": limit}
    if run_params:
        params.update(run_params)
    topic_config = {
        "model": settings.topic_model,
        "max_topics": settings.topic_max,
        "seed": settings.random_seed,
        "min_cluster_size": settings.bertopic_min_cluster_size,
        "umap": {
            "n_neighbors": 15,
            "n_components": 5,
            "min_dist": 0.0,
            "metric": "cosine",
            "n_jobs": 1,
        },
        "hdbscan": {"cluster_selection_method": "eom", "core_dist_n_jobs": 1},
        "vectorizer": {"ngram_range": [1, 2], "stop_words": "english", "top_n": 8},
        "matching": {
            "threshold": settings.match_threshold,
            "review_threshold": settings.match_review_threshold,
            "margin": settings.match_margin,
        },
    }
    run = Run(
        embedder=settings.embedder,
        embedder_revision=settings.embedder_revision,
        topic_model=settings.topic_model,
        topic_model_revision=settings.topic_model_revision,
        describer=settings.describer,
        classifier=settings.classifier,
        random_seed=settings.random_seed,
        params=params,
        git_revision=_git_revision(),
        component_manifest={
            "topic_config": topic_config,
            "packages": _package_versions(),
            "embedding": {
                "name": settings.embedder,
                "model": settings.sentence_transformer_model,
                "revision": settings.embedder_revision,
                "dimension": settings.embedding_dim,
                "normalize": True,
            },
        },
        prompt_manifest={},
        usage_metrics={"llm_calls": 0, "max_llm_calls": settings.max_llm_calls},
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def run_pipeline(
    query: str,
    *,
    session: Session,
    limit: int = 50,
    connector: Connector | None = None,
    raw_docs: list[RawDocument] | None = None,
    settings: Settings | None = None,
    run_params: dict | None = None,
    language: str | None = None,
    run: Run | None = None,
    progress: ProgressCallback | None = None,
) -> Run:
    """Execute one full pipeline run and persist all artifacts. Returns the Run.

    Documents come either from ``raw_docs`` (e.g. a deep-research crawl) or, if not
    provided, from a single ``connector`` fetch for ``query`` (the simple path).
    """
    settings = settings or get_settings()
    language = language or settings.language

    run = run or create_run(
        session,
        query=query,
        settings=settings,
        limit=limit,
        run_params=run_params,
    )

    try:
        if progress:
            progress("ingesting", 30, "Documents are being normalized and deduplicated", None)
        # 1. Ingest
        if raw_docs is None:
            connector = connector or OpenAlexConnector()
            raw_docs = connector.fetch(query, limit=limit)
        new_docs = _persist_documents(session, raw_docs)
        run.corpus_cutoff = datetime.now(UTC)
        docs, corpus_hash = materialize_corpus(
            session,
            run_id=run.id,
            cutoff=run.corpus_cutoff,
            new_document_ids={document.id for document in new_docs},
        )
        run.corpus_hash = corpus_hash
        if progress:
            progress(
                "corpus",
                42,
                "Cumulative corpus snapshot materialized",
                {
                    "documents": len(docs),
                    "new_documents": len(new_docs),
                    "carried_forward": max(0, len(docs) - len(new_docs)),
                },
            )

        if not docs:
            run.status = "completed"
            run.finished_at = datetime.now(UTC)
            session.add(run)
            session.commit()
            session.refresh(run)
            if progress:
                progress("completed", 100, "Run completed without eligible documents", None)
            return run

        texts = [d.text for d in docs]

        # 2. Embed (one chunk per document in v0)
        if progress:
            progress("embedding", 52, "Semantic document embeddings are being generated", None)
        embedder = get_embedder(
            settings.embedder,
            settings.embedding_dim,
            model_name=settings.sentence_transformer_model,
            model_revision=settings.embedder_revision,
        )
        embeddings = embed_documents_cached(
            session,
            docs,
            embedder=embedder,
            model_name=settings.embedder,
            model_revision=settings.embedder_revision,
        )

        # 3. Topic modeling
        if progress:
            progress("clustering", 64, "BERTopic is clustering the cumulative corpus", None)
        modeler = get_topic_modeler(
            settings.topic_model,
            max_topics=settings.topic_max,
            random_state=settings.random_seed,
            min_cluster_size=settings.bertopic_min_cluster_size,
        )
        result = modeler.fit(texts, embeddings)
        memberships = session.exec(
            select(RunDocument)
            .where(RunDocument.run_id == run.id)
            .order_by(RunDocument.position)
        ).all()
        probabilities = result.probabilities or [None] * len(result.labels)
        for membership, label, probability in zip(
            memberships, result.labels, probabilities, strict=True
        ):
            membership.topic_index = label if label >= 0 else None
            membership.is_outlier = label < 0
            membership.membership_probability = probability
            session.add(membership)

        # 4. Time series per topic
        timepoints = build_topic_timepoints(
            [d.published_at for d in docs], result.labels
        )
        corpus_timepoints = build_topic_timepoints(
            [d.published_at for d in docs], [0] * len(docs)
        ).get(0, {})

        # 4b. Topic centroids -> emergence vs. the previous run (ADR-19)
        centroids = {
            info.topic_index: topic_centroid(
                embeddings, result.labels, info.topic_index
            )
            for info in result.topics
            if info.topic_index >= 0
        }
        emergence = compute_emergence(
            centroids, _previous_topic_centroids(session, run.id)
        )

        # 5. Topics + trends + descriptions (RAG retrieval over pgvector, ADR-11/14)
        if progress:
            progress(
                "analyzing",
                76,
                "Topics are being described, scored and classified",
                {
                    "detected_topics": len(
                        [topic for topic in result.topics if topic.topic_index >= 0]
                    )
                },
            )
        describer = get_describer(settings.describer)
        classifier = get_classifier(settings.classifier)
        fallback_describer = get_describer("template")
        fallback_classifier = get_classifier("heuristic")
        llm_calls = 0
        retriever = PgVectorRetriever(session, [d.id for d in docs])
        n_topics = 0
        for info in result.topics:
            if info.topic_index < 0:  # outliers are not trends
                continue
            n_topics += 1
            centroid = centroids[info.topic_index]
            region, country = _dominant_geo(
                [
                    d
                    for d, label in zip(docs, result.labels, strict=True)
                    if label == info.topic_index
                ]
            )
            topic = Topic(
                run_id=run.id,
                topic_index=info.topic_index,
                label=info.label,
                keywords=info.keywords,
                size=info.size,
                region=region,
                country=country,
                centroid=centroid.tolist() if centroid.size else None,
            )
            session.add(topic)
            session.flush()
            session.refresh(topic)

            tp = complete_quarters(
                timepoints.get(info.topic_index, {}),
                max_periods=settings.timeseries_max_quarters,
            )
            prevalence = topic_prevalence(tp, corpus_timepoints)
            for period, count in sorted(tp.items()):
                session.add(
                    TopicTimepoint(
                        topic_id=topic.id,
                        period=period,
                        doc_count=count,
                        prevalence=prevalence.get(period, 0.0),
                    )
                )

            # Retrieve grounding evidence by vector similarity to the topic centroid;
            # fall back to the in-cluster documents if retrieval yields nothing.
            representative: list[dict] = []
            if centroid.size:
                try:
                    representative = retriever.retrieve(centroid, k=6)
                except Exception:
                    logger.warning(
                        "Retrieval failed for topic %s; falling back to in-cluster docs",
                        info.topic_index,
                        exc_info=True,
                    )
                    representative = []
            if not representative:
                representative = [
                    {"title": d.title, "url": d.url, "text": d.text}
                    for d, label in zip(docs, result.labels, strict=True)
                    if label == info.topic_index
                ][:6]
            active_describer = describer
            if settings.describer == "openai":
                if llm_calls >= settings.max_llm_calls:
                    active_describer = fallback_describer
                else:
                    llm_calls += 1
            description = active_describer.describe(
                info.keywords, representative, language=language
            )
            topic_emergence = emergence.get(info.topic_index)
            maturity = classify_maturity(tp, emergence=topic_emergence)

            trend = Trend(
                topic_id=topic.id,
                run_id=run.id,
                title=description.title,
                summary=description.summary,
                maturity=maturity,
                emergence=topic_emergence,
                evidence=description.evidence,
            )
            session.add(trend)
            session.flush()
            session.refresh(trend)

            # 6/7. PESTEL + category classification and impact/urgency scoring, from
            # which the Act/Prepare/Watch radar stage is derived (ADR-25/26/27).
            n_sources = len(
                {
                    d.source_id
                    for d, label in zip(docs, result.labels, strict=True)
                    if label == info.topic_index
                }
            )
            active_classifier = classifier
            if settings.classifier == "openai":
                if llm_calls >= settings.max_llm_calls:
                    active_classifier = fallback_classifier
                else:
                    llm_calls += 1
            classification = active_classifier.classify(
                TrendSignal(
                    keywords=info.keywords or [],
                    title=description.title,
                    summary=description.summary,
                    maturity=maturity,
                    emergence=topic_emergence,
                    size=info.size,
                    n_sources=max(1, n_sources),
                    timepoints=tp,
                    evidence=description.evidence,
                )
            )
            session.add(
                TrendAssessment(
                    trend_id=trend.id,
                    pestel=classification.pestel,
                    category=classification.category,
                    impact=classification.impact,
                    urgency=classification.urgency,
                    uncertainty=classification.uncertainty,
                    radar_stage=radar_stage(
                        classification.impact, classification.urgency
                    ),
                    rationale=classification.rationale,
                )
            )

        session.flush()
        if progress:
            progress(
                "matching",
                90,
                "Topics are being matched against the existing trend portfolio",
                {"topics": n_topics},
            )
        reconcile_run(
            session,
            run_id=run.id,
            threshold=settings.match_threshold,
            review_threshold=settings.match_review_threshold,
            margin_threshold=settings.match_margin,
        )
        run.status = "completed"
        run.finished_at = datetime.now(UTC)
        run.n_documents = len(docs)
        run.n_topics = n_topics
        run.usage_metrics = {
            **(run.usage_metrics or {}),
            "llm_calls": llm_calls,
            "max_llm_calls": settings.max_llm_calls,
        }
        session.add(run)
        session.commit()
        session.refresh(run)
        if progress:
            progress(
                "completed",
                100,
                "Run completed and portfolio history updated",
                {"documents": len(docs), "topics": n_topics},
            )
        return run
    except Exception as exc:
        # The session may be in a pending-rollback state (e.g. a failed flush),
        # so roll back FIRST - before touching any ORM attribute or committing -
        # otherwise the status commit raises PendingRollbackError and masks the
        # original exception.
        session.rollback()
        run.status = "failed"
        run.finished_at = datetime.now(UTC)
        run.error = f"{type(exc).__name__}: {exc}"[:500]
        session.add(run)
        session.commit()
        if progress:
            progress("failed", 100, "Run failed", {"error": run.error})
        logger.exception("Pipeline run %s failed", run.id)
        raise
