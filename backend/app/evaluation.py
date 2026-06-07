"""Evaluation: overlap of discovered trends vs. a manual reference list (§11).

This implements the *strategic relevance* dimension of the evaluation methodology: how
well the system rediscovers the trends a human team already identified, and which
additional trends it surfaces. The match is a deterministic lexical Jaccard over the
combined title+keyword token sets, so the metric is reproducible and needs no LLM.

* **recall**    = matched references / all references (coverage of the manual list)
* **precision** = matched run trends / all run trends (how much of the output is
  "known-relevant"); deliberately *not* a quality ceiling - unmatched trends may be
  genuine novel discoveries, reported separately as ``novel``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_WORD = re.compile(r"[a-z0-9]{3,}")
_STOP = {
    "and", "the", "for", "with", "from", "into", "trend", "trends", "building",
    "buildings", "construction",
}


def _tokens(title: str, keywords: list[str] | None) -> set[str]:
    text = f"{title} {' '.join(keywords or [])}".lower()
    return {w for w in _WORD.findall(text) if w not in _STOP}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class TrendLike:
    """Minimal shape needed for matching (works for run trends and references)."""

    id: int
    title: str
    keywords: list[str] = field(default_factory=list)


@dataclass
class MatchPair:
    reference_id: int
    reference_title: str
    trend_id: int
    trend_title: str
    score: float


@dataclass
class OverlapResult:
    n_references: int
    n_trends: int
    matches: list[MatchPair]
    missed_references: list[TrendLike]  # in reference list, not found by the system
    novel_trends: list[TrendLike]  # found by the system, not in the reference list
    threshold: float

    @property
    def n_matched_references(self) -> int:
        return len({m.reference_id for m in self.matches})

    @property
    def recall(self) -> float:
        return self.n_matched_references / self.n_references if self.n_references else 0.0

    @property
    def precision(self) -> float:
        matched_trends = len({m.trend_id for m in self.matches})
        return matched_trends / self.n_trends if self.n_trends else 0.0


def compute_overlap(
    trends: list[TrendLike],
    references: list[TrendLike],
    *,
    threshold: float = 0.18,
) -> OverlapResult:
    """Greedy best-match each reference to a run trend above ``threshold``."""
    trend_tokens = {t.id: _tokens(t.title, t.keywords) for t in trends}
    ref_tokens = {r.id: _tokens(r.title, r.keywords) for r in references}

    matches: list[MatchPair] = []
    matched_trend_ids: set[int] = set()
    missed: list[TrendLike] = []

    for ref in references:
        best: tuple[float, TrendLike | None] = (0.0, None)
        for trend in trends:
            score = _jaccard(ref_tokens[ref.id], trend_tokens[trend.id])
            if score > best[0]:
                best = (score, trend)
        score, trend = best
        if trend is not None and score >= threshold:
            matches.append(
                MatchPair(
                    reference_id=ref.id,
                    reference_title=ref.title,
                    trend_id=trend.id,
                    trend_title=trend.title,
                    score=round(score, 3),
                )
            )
            matched_trend_ids.add(trend.id)
        else:
            missed.append(ref)

    novel = [t for t in trends if t.id not in matched_trend_ids]
    return OverlapResult(
        n_references=len(references),
        n_trends=len(trends),
        matches=matches,
        missed_references=missed,
        novel_trends=novel,
        threshold=threshold,
    )
