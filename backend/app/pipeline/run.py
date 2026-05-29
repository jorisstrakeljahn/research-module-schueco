"""End-to-end pipeline orchestration: ingest -> embed -> topics -> describe -> persist.

A single invocation corresponds to one :class:`~app.models.Run` snapshot, which makes
the process reproducible and enables run-to-run delta comparison (ADR-16/19).
"""

from __future__ import annotations

from datetime import UTC, datetime

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
from app.pipeline.describe import get_describer
from app.pipeline.embeddings import get_embedder
from app.pipeline.timeseries import build_topic_timepoints, classify_maturity
from app.pipeline.topics import get_topic_modeler


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
) -> Run:
    """Execute one full pipeline run and persist all artifacts. Returns the Run.

    Documents come either from ``raw_docs`` (e.g. a deep-research crawl) or, if not
    provided, from a single ``connector`` fetch for ``query`` (the simple path).
    """
    settings = settings or get_settings()

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
        modeler = get_topic_modeler(settings.topic_model)
        result = modeler.fit(texts, embeddings)

        # 4. Time series per topic
        timepoints = build_topic_timepoints(
            [d.published_at for d in docs], result.labels
        )

        # 5. Topics + trends + descriptions
        describer = get_describer(settings.describer)
        n_topics = 0
        for info in result.topics:
            if info.topic_index < 0:  # outliers are not trends
                continue
            n_topics += 1
            topic = Topic(
                run_id=run.id,
                topic_index=info.topic_index,
                label=info.label,
                keywords=info.keywords,
                size=info.size,
            )
            session.add(topic)
            session.commit()
            session.refresh(topic)

            tp = timepoints.get(info.topic_index, {})
            for period, count in sorted(tp.items()):
                session.add(
                    TopicTimepoint(topic_id=topic.id, period=period, doc_count=count)
                )

            representative = [
                {"title": d.title, "url": d.url, "text": d.text}
                for d, label in zip(docs, result.labels, strict=True)
                if label == info.topic_index
            ][:6]
            description = describer.describe(info.keywords, representative)
            maturity = classify_maturity(tp)

            trend = Trend(
                topic_id=topic.id,
                run_id=run.id,
                title=description.title,
                summary=description.summary,
                maturity=maturity,
                evidence=description.evidence,
            )
            session.add(trend)
            session.commit()
            session.refresh(trend)
            session.add(TrendAssessment(trend_id=trend.id, radar_stage="watch"))

        session.commit()

        run.status = "completed"
        run.finished_at = datetime.now(UTC)
        run.n_documents = len(docs)
        run.n_topics = n_topics
        session.add(run)
        session.commit()
        session.refresh(run)
        return run
    except Exception:
        run.status = "failed"
        run.finished_at = datetime.now(UTC)
        session.add(run)
        session.commit()
        raise
