"""Temporal trend dynamics (project plan §6.1, ADR-19).

A trend is, by definition, a development over time. Rather than waiting months for
live data, we build a retrospective time series from each document's
``published_at`` date and derive a maturity level from volume and growth.
"""

from __future__ import annotations

from datetime import datetime


def to_period(dt: datetime) -> str:
    """Map a datetime to a quarter label, e.g. ``2024-Q2``."""
    quarter = (dt.month - 1) // 3 + 1
    return f"{dt.year}-Q{quarter}"


def build_topic_timepoints(
    published_ats: list[datetime | None], labels: list[int]
) -> dict[int, dict[str, int]]:
    """Return ``{topic_index: {period: doc_count}}`` (outliers, label -1, ignored)."""
    result: dict[int, dict[str, int]] = {}
    for dt, label in zip(published_ats, labels, strict=True):
        if label < 0 or dt is None:
            continue
        period = to_period(dt)
        result.setdefault(label, {})
        result[label][period] = result[label].get(period, 0) + 1
    return result


def classify_maturity(
    timepoints: dict[str, int],
    *,
    emergence: float | None = None,
    weak_max: int = 4,
    growth_threshold: float = 0.5,
    established_span: int = 6,
    megatrend_min: int = 15,
    novel_threshold: float = 0.6,
) -> str:
    """Heuristic maturity from a topic's quarterly counts and its emergence score.

    The volume/growth axis gives a base level - weak_signal: very low volume;
    emerging: clear recent growth; megatrend: high volume sustained over many quarters;
    established: otherwise present and stable. The semantic emergence axis (novelty vs.
    the previous run, see :mod:`app.pipeline.emergence`) then corrects it: a topic that
    is semantically new yet already carries volume reads as *emerging* rather than
    *established* (Mühlroth & Grottke, 2020).
    """
    if not timepoints:
        return "weak_signal"

    total = sum(timepoints.values())
    if total <= weak_max:
        level = "weak_signal"
    else:
        periods = sorted(timepoints)
        span = len(periods)
        mid = span // 2
        older = sum(timepoints[p] for p in periods[:mid]) or 1
        recent = sum(timepoints[p] for p in periods[mid:])
        growth = (recent - older) / older

        # Megatrend = sustained volume across a long span. ``total`` counts dated
        # documents only, so the long-span gate (not raw volume) is the decisive
        # discriminator versus a recent emerging spike.
        if total >= megatrend_min and span >= established_span:
            level = "megatrend"
        elif growth >= growth_threshold:
            level = "emerging"
        else:
            level = "established"

    # Emergence override: a semantically novel topic is not "established" yet.
    if emergence is not None and emergence >= novel_threshold and level == "established":
        return "emerging"
    return level
