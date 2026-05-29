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
    weak_max: int = 4,
    growth_threshold: float = 0.5,
    established_span: int = 6,
    megatrend_min: int = 30,
) -> str:
    """Heuristic maturity from a topic's quarterly counts.

    weak_signal: very low volume. emerging: clear recent growth. megatrend: high
    volume sustained over many quarters. established: otherwise present and stable.
    """
    if not timepoints:
        return "weak_signal"

    total = sum(timepoints.values())
    if total <= weak_max:
        return "weak_signal"

    periods = sorted(timepoints)
    span = len(periods)
    mid = span // 2
    older = sum(timepoints[p] for p in periods[:mid]) or 1
    recent = sum(timepoints[p] for p in periods[mid:])
    growth = (recent - older) / older

    if total >= megatrend_min and span >= established_span:
        return "megatrend"
    if growth >= growth_threshold:
        return "emerging"
    return "established"
