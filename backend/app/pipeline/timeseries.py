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


def complete_quarters(
    timepoints: dict[str, int], *, max_periods: int | None = None
) -> dict[str, int]:
    """Fill missing quarters, optionally limiting the operational analysis window.

    A single old paper must not create decades of zeroes or dominate current growth.
    ``max_periods`` therefore anchors a rolling window at the latest observation while
    preserving the original publication dates inside that window.
    """
    if not timepoints:
        return {}
    first, last = min(timepoints), max(timepoints)
    year, quarter = int(first[:4]), int(first[-1])
    end_year, end_quarter = int(last[:4]), int(last[-1])
    if max_periods is not None:
        if max_periods < 1:
            raise ValueError("max_periods must be positive")
        start_index = end_year * 4 + end_quarter - 1 - (max_periods - 1)
        window_year, window_quarter_zero = divmod(start_index, 4)
        window_start = (window_year, window_quarter_zero + 1)
        if (year, quarter) < window_start:
            year, quarter = window_start
    completed: dict[str, int] = {}
    while (year, quarter) <= (end_year, end_quarter):
        period = f"{year}-Q{quarter}"
        completed[period] = timepoints.get(period, 0)
        quarter += 1
        if quarter == 5:
            year, quarter = year + 1, 1
    return completed


def topic_prevalence(
    topic_counts: dict[str, int], corpus_counts: dict[str, int]
) -> dict[str, float]:
    return {
        period: count / corpus_counts.get(period, 1)
        if corpus_counts.get(period, 0)
        else 0.0
        for period, count in complete_quarters(topic_counts).items()
    }


def growth_ratio(timepoints: dict[str, int]) -> float:
    """Signed recent-vs-older growth ratio of quarterly counts (split at the midpoint).

    Shared with :mod:`app.pipeline.classify`, which clamps the result at 0 for its
    urgency signal; the maturity heuristic uses the signed value directly.
    """
    periods = sorted(timepoints)
    mid = len(periods) // 2
    older = sum(timepoints[p] for p in periods[:mid]) or 1
    recent = sum(timepoints[p] for p in periods[mid:])
    return (recent - older) / older


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
        span = len(timepoints)
        growth = growth_ratio(timepoints)

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


def stabilize_maturity(previous: str | None, proposed: str, *, evidence_count: int) -> str:
    """Require meaningful evidence before a multi-level maturity jump."""
    levels = ["weak_signal", "emerging", "established", "megatrend"]
    if previous not in levels or proposed not in levels:
        return proposed
    old, new = levels.index(previous), levels.index(proposed)
    if abs(new - old) > 1 and evidence_count < 8:
        return levels[old + (1 if new > old else -1)]
    return proposed
