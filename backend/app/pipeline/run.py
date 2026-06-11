"""End-to-end pipeline orchestration: ingest -> embed -> topics -> describe -> persist.

A single invocation corresponds to one :class:`~app.models.Run` snapshot, which makes
the process reproducible and enables run-to-run delta comparison (ADR-16/19).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import numpy as np
from sqlmodel import Session, select

from app.config import Settings, get_settings
from app.ingestion.base import Connector, RawDocument
from app.ingestion.openalex import OpenAlexConnector
from app.models import (
    Chunk,
    Document,
    Run,
    Source,
    Topic,
    TopicTimepoint,
    Trend,
    TrendAssessment,
)
from app.pipeline.classify import TrendSignal, get_classifier, radar_stage
from app.pipeline.describe import get_describer
from app.pipeline.embeddings import get_embedder
from app.pipeline.emergence import compute_emergence
from app.pipeline.retrieval import PgVectorRetriever, topic_centroid
from app.pipeline.timeseries import build_topic_timepoints, classify_maturity
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
    session.commit()
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
        doc = Document(
            source_id=source.id,
            external_id=raw.external_id,
            title=raw.title,
            text=raw.text,
            url=raw.url,
            published_at=raw.published_at,
            language=raw.language,
            region=raw.region,
            country=raw.country,
        )
        session.add(doc)
        docs.append(doc)
    session.commit()
    for doc in docs:
        session.refresh(doc)
    return docs


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
) -> Run:
    """Execute one full pipeline run and persist all artifacts. Returns the Run.

    Documents come either from ``raw_docs`` (e.g. a deep-research crawl) or, if not
    provided, from a single ``connector`` fetch for ``query`` (the simple path).
    """
    settings = settings or get_settings()
    language = language or settings.language

    params = {"query": query, "limit": limit}
    if run_params:
        params.update(run_params)

    run = Run(
        embedder=settings.embedder,
        topic_model=settings.topic_model,
        describer=settings.describer,
        params=params,
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    try:
        # 1. Ingest
        if raw_docs is None:
            connector = connector or OpenAlexConnector()
            raw_docs = connector.fetch(query, limit=limit)
        docs = _persist_documents(session, raw_docs)

        if not docs:
            run.status = "completed"
            run.finished_at = datetime.now(UTC)
            session.add(run)
            session.commit()
            session.refresh(run)
            return run

        texts = [d.text for d in docs]

        # 2. Embed (one chunk per document in v0)
        embedder = get_embedder(settings.embedder, settings.embedding_dim)
        embeddings = embedder.embed(texts)
        for doc, vector in zip(docs, embeddings, strict=True):
            session.add(
                Chunk(document_id=doc.id, chunk_index=0, text=doc.text,
                      embedding=vector.tolist())
            )
        session.commit()

        # 3. Topic modeling
        modeler = get_topic_modeler(settings.topic_model, max_topics=settings.topic_max)
        result = modeler.fit(texts, embeddings)

        # 4. Time series per topic
        timepoints = build_topic_timepoints(
            [d.published_at for d in docs], result.labels
        )

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
        describer = get_describer(settings.describer)
        classifier = get_classifier(settings.classifier)
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
            session.commit()
            session.refresh(topic)

            tp = timepoints.get(info.topic_index, {})
            for period, count in sorted(tp.items()):
                session.add(
                    TopicTimepoint(topic_id=topic.id, period=period, doc_count=count)
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
            description = describer.describe(
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
            session.commit()
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
            classification = classifier.classify(
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

        session.commit()

        run.status = "completed"
        run.finished_at = datetime.now(UTC)
        run.n_documents = len(docs)
        run.n_topics = n_topics
        session.add(run)
        session.commit()
        session.refresh(run)
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
        logger.exception("Pipeline run %s failed", run.id)
        raise
