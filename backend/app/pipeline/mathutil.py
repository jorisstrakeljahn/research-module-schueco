"""Small numeric helpers shared across the pipeline."""

from __future__ import annotations

import numpy as np


def l2_normalize(matrix: np.ndarray) -> np.ndarray:
    """L2-normalize each row; a 1-D input is treated as a single row."""
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms
