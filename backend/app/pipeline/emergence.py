"""Emergence measurement (project plan §6.1 / Kap. 2.3, ADR-19).

Following Mühlroth & Grottke (2020), a topic is analysed along two axes: *trend*
(volume growth over time, see :mod:`app.pipeline.timeseries`) and *emergence*
(semantic novelty). Emergence is measured across run generations: a topic whose
centroid is dissimilar to every topic of the previous run is novel/emergent; one that
closely matches a prior topic is a continuation. Without a previous run there is no
baseline, so emergence is undefined.
"""

from __future__ import annotations

import numpy as np


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def compute_emergence(
    current_centroids: dict[int, np.ndarray],
    previous_centroids: list[np.ndarray],
) -> dict[int, float | None]:
    """Return ``{topic_index: novelty}`` in ``[0, 1]``; ``None`` if no baseline exists.

    Novelty = ``1 - max cosine similarity`` to any previous-run topic centroid: ``1.0``
    means semantically unseen, ``0.0`` means an exact continuation of a prior topic.
    """
    if not previous_centroids:
        return {idx: None for idx in current_centroids}

    prev = _l2_normalize(np.vstack([np.asarray(c) for c in previous_centroids]))
    result: dict[int, float | None] = {}
    for idx, centroid in current_centroids.items():
        vec = _l2_normalize(np.asarray(centroid))[0]
        sims = prev @ vec
        max_sim = float(np.max(sims)) if sims.size else 0.0
        result[idx] = max(0.0, min(1.0, 1.0 - max_sim))
    return result
