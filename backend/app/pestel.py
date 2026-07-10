"""Evidence-grounded six-dimensional PESTEL analysis for portfolio trends."""

from __future__ import annotations

import math
import re
from collections import Counter

from sqlmodel import Session, select

from app.models import (
    PESTEL_DIMENSIONS,
    Document,
    RunDocument,
    Source,
    Topic,
    Trend,
    TrendOccurrence,
)
from app.pipeline.classify import _PESTEL_LEXICON
from app.schemas import (
    PestelAnalysisOut,
    PestelDimensionAnalysisOut,
    TrendEvidenceOut,
)

TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z-]{2,}")


def build_pestel_analysis(
    session: Session,
    *,
    canonical_id: str,
    occurrence: TrendOccurrence,
) -> PestelAnalysisOut:
    """Analyze all six PESTEL dimensions against the latest cluster documents."""
    trend = session.get(Trend, occurrence.trend_id)
    topic = session.get(Topic, trend.topic_id) if trend else None
    if trend is None or topic is None:
        raise ValueError("Occurrence snapshot is unavailable")

    rows = session.exec(
        select(Document, Source)
        .join(RunDocument, RunDocument.document_id == Document.id)
        .join(Source, Source.id == Document.source_id, isouter=True)
        .where(
            RunDocument.run_id == occurrence.run_id,
            RunDocument.topic_index == topic.topic_index,
            RunDocument.is_outlier.is_(False),
        )
        .order_by(Document.published_at.desc(), Document.id)
    ).all()
    corpus = [
        {
            "title": document.title,
            "text": document.text,
            "url": document.url,
            "published_at": document.published_at,
            "source": source.name if source else None,
        }
        for document, source in rows
    ]
    if not corpus:
        corpus = [
            {
                "title": item.get("title", ""),
                "text": item.get("title", ""),
                "url": item.get("url"),
                "published_at": None,
                "source": item.get("source"),
            }
            for item in (trend.evidence or [])
            if item.get("title")
        ]
    total = len(corpus)
    dimensions: list[PestelDimensionAnalysisOut] = []
    for dimension in PESTEL_DIMENSIONS:
        lexicon = _PESTEL_LEXICON[dimension]
        matches: list[tuple[int, dict, set[str]]] = []
        term_counts: Counter[str] = Counter()
        for item in corpus:
            tokens = {
                token.casefold()
                for token in TOKEN_RE.findall(f"{item['title']} {item['text']}")
            }
            terms = tokens & lexicon
            if not terms:
                continue
            term_counts.update(terms)
            matches.append((len(terms), item, terms))
        matches.sort(
            key=lambda item: (
                item[0],
                item[1]["published_at"] is not None,
                item[1]["published_at"],
            ),
            reverse=True,
        )
        coverage = len(matches) / total if total else 0.0
        relevance = round(min(10.0, 10.0 * math.sqrt(coverage)), 1)
        evidence = [
            TrendEvidenceOut(
                title=item["title"],
                url=item["url"],
                source=item["source"],
                published_at=(
                    item["published_at"].date().isoformat()
                    if item["published_at"]
                    else None
                ),
                run_id=occurrence.run_id,
            )
            for _, item, _ in matches[:3]
        ]
        dimensions.append(
            PestelDimensionAnalysisOut(
                dimension=dimension,
                relevance=relevance,
                matched_documents=len(matches),
                total_documents=total,
                signal_terms=[term for term, _ in term_counts.most_common(5)],
                evidence=evidence,
            )
        )
    return PestelAnalysisOut(
        trend_id=canonical_id,
        run_id=occurrence.run_id,
        dimensions=dimensions,
    )
