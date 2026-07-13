#!/usr/bin/env python3
"""Re-describe, re-classify and translate every demo trend with the LLM.

One-off curation pass for the demo database: each run trend gets a fresh
LLM-generated title/summary (grounded in its cluster documents), a fresh PESTEL/
impact/urgency classification with rationale, plus a stored DE and EN version.
Canonical portfolio trends are then synced from their latest occurrence.

Usage: uv run python scripts/eval/reassess_portfolio.py --apply
"""

from __future__ import annotations

import argparse
from collections import Counter

from sqlmodel import Session, select

from app.config import get_settings
from app.db import get_engine
from app.models import (
    CanonicalTrend,
    Document,
    RunDocument,
    Source,
    Topic,
    TopicTimepoint,
    Trend,
    TrendAssessment,
    TrendOccurrence,
    TrendTranslation,
)
from app.pipeline.classify import TrendSignal, get_classifier, radar_stage
from app.pipeline.describe import get_describer
from app.pipeline.matching import proposed_values
from app.pipeline.translate import resolve_translator, translations_for_trend


def _topic_documents(session: Session, run_id: int, topic_index: int) -> list[dict]:
    rows = session.exec(
        select(Document, Source)
        .join(RunDocument, RunDocument.document_id == Document.id)
        .join(Source, Source.id == Document.source_id, isouter=True)
        .where(
            RunDocument.run_id == run_id,
            RunDocument.topic_index == topic_index,
            RunDocument.is_outlier.is_(False),
        )
        .order_by(Document.published_at.desc(), Document.id)
    ).all()
    return [
        {
            "title": document.title,
            "text": document.text,
            "url": document.url,
            "source": source.name if source else None,
        }
        for document, source in rows
    ]


def reassess_trend(
    session: Session, trend: Trend, describer, classifier, translator
) -> tuple[Trend, TrendAssessment]:
    topic = session.get(Topic, trend.topic_id)
    docs = _topic_documents(session, trend.run_id, topic.topic_index)
    representative = docs[:8] or [
        {"title": e.get("title", ""), "text": e.get("title", ""), "url": e.get("url")}
        for e in (trend.evidence or [])
        if e.get("title")
    ]
    description = describer.describe(topic.keywords or [], representative, language="en")

    timepoints = {
        point.period: point.doc_count
        for point in session.exec(
            select(TopicTimepoint).where(TopicTimepoint.topic_id == topic.id)
        ).all()
    }
    n_sources = len({d["source"] for d in docs if d["source"]}) or 1
    classification = classifier.classify(
        TrendSignal(
            keywords=topic.keywords or [],
            title=description.title,
            summary=description.summary,
            maturity=trend.maturity,
            emergence=trend.emergence,
            size=topic.size,
            n_sources=n_sources,
            timepoints=timepoints,
            evidence=(
                [{"title": d["title"]} for d in docs if d["title"]]
                or (trend.evidence or [])
            ),
            language="en",
        )
    )

    trend.title = description.title
    trend.summary = description.summary
    if description.evidence:
        trend.evidence = description.evidence
    session.add(trend)

    assessment = session.exec(
        select(TrendAssessment).where(TrendAssessment.trend_id == trend.id)
    ).first()
    if assessment is None:
        assessment = TrendAssessment(trend_id=trend.id)
    assessment.pestel = classification.pestel
    assessment.category = classification.category
    assessment.impact = classification.impact
    assessment.urgency = classification.urgency
    assessment.uncertainty = classification.uncertainty
    assessment.radar_stage = radar_stage(classification.impact, classification.urgency)
    assessment.rationale = classification.rationale
    session.add(assessment)

    # Replace any stale cached translations with a fresh bilingual pair.
    for row in session.exec(
        select(TrendTranslation).where(TrendTranslation.trend_id == trend.id)
    ).all():
        session.delete(row)
    session.add(
        TrendTranslation(
            trend_id=trend.id,
            language="en",
            title=trend.title,
            summary=trend.summary,
            rationale=assessment.rationale,
        )
    )
    german = translator.translate(
        title=trend.title,
        summary=trend.summary,
        rationale=assessment.rationale,
        language="de",
    )
    session.add(
        TrendTranslation(
            trend_id=trend.id,
            language="de",
            title=german.title,
            summary=german.summary,
            rationale=german.rationale,
        )
    )
    session.flush()
    return trend, assessment


def calibrate_scores(
    session: Session, pairs: list[tuple[Trend, TrendAssessment]]
) -> None:
    """Portfolio-level percentile calibration of impact/urgency.

    The LLM scores absolute importance, which pins most established building
    trends at 8-9 and leaves the radar's outer ring empty. Rescaling by rank
    keeps the model's relative ordering but spreads the portfolio across the
    full Act/Prepare/Watch scale - standard practice for relative prioritization
    within a foresight portfolio.
    """
    n = len(pairs)
    if n < 2:
        return

    def rescale(ranked: list[tuple[Trend, TrendAssessment]], attr: str) -> None:
        for index, (_, assessment) in enumerate(ranked):
            value = 3.2 + 6.3 * index / (n - 1)
            setattr(assessment, attr, round(value, 1))

    by_impact = sorted(
        pairs,
        key=lambda pair: (
            pair[1].impact or 0,
            session.get(Topic, pair[0].topic_id).size,
            pair[0].id,
        ),
    )
    rescale(by_impact, "impact")
    by_urgency = sorted(
        pairs,
        key=lambda pair: (
            pair[1].urgency or 0,
            pair[0].emergence or 0,
            pair[0].id,
        ),
    )
    rescale(by_urgency, "urgency")
    for _, assessment in pairs:
        assessment.uncertainty = round(assessment.uncertainty or 5.0, 1)
        assessment.radar_stage = radar_stage(assessment.impact, assessment.urgency)
        session.add(assessment)
    session.flush()


def sync_canonicals(session: Session) -> None:
    for canonical in session.exec(select(CanonicalTrend)).all():
        occurrence = session.exec(
            select(TrendOccurrence)
            .where(TrendOccurrence.canonical_trend_id == canonical.id)
            .order_by(TrendOccurrence.run_id.desc(), TrendOccurrence.id.desc())
        ).first()
        if occurrence is None:
            continue
        trend = session.get(Trend, occurrence.trend_id)
        assessment = session.exec(
            select(TrendAssessment).where(TrendAssessment.trend_id == trend.id)
        ).first()
        for field, value in proposed_values(trend, assessment).items():
            setattr(canonical, field, value)
        canonical.translations = translations_for_trend(
            session,
            trend.id,
            fallback_title=trend.title,
            fallback_summary=trend.summary,
            fallback_rationale=assessment.rationale if assessment else None,
        )
        session.add(canonical)


def print_distribution(session: Session) -> None:
    canonicals = session.exec(
        select(CanonicalTrend).where(CanonicalTrend.status == "active")
    ).all()
    sectors = Counter((c.pestel or ["-"])[0] for c in canonicals)
    stages = Counter(c.radar_stage or "-" for c in canonicals)
    categories = Counter(c.category or "-" for c in canonicals)
    print(f"\nActive portfolio trends: {len(canonicals)}")
    print(f"PESTEL sectors: {dict(sectors)}")
    print(f"Radar stages:   {dict(stages)}")
    print(f"Categories:     {dict(categories)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Persist the changes.")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY is required for the reassessment pass")
    describer = get_describer("openai")
    classifier = get_classifier("openai")
    translator = resolve_translator(settings)

    with Session(get_engine()) as session:
        trends = session.exec(select(Trend).order_by(Trend.id)).all()
        print(f"Reassessing {len(trends)} trends ...")
        pairs: list[tuple[Trend, TrendAssessment]] = []
        for trend in trends:
            pairs.append(
                reassess_trend(session, trend, describer, classifier, translator)
            )
        calibrate_scores(session, pairs)
        for trend, assessment in pairs:
            print(
                f"  trend {trend.id} (run {trend.run_id}): {trend.title}\n"
                f"    pestel={assessment.pestel} category={assessment.category} "
                f"impact={assessment.impact} urgency={assessment.urgency} "
                f"stage={assessment.radar_stage}"
            )
        sync_canonicals(session)
        print_distribution(session)
        if args.apply:
            session.commit()
            print("\nApplied.")
        else:
            session.rollback()
            print("\nDry run only - re-run with --apply to persist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
