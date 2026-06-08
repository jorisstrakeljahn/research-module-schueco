"""Tests for the cross-run emergence (semantic novelty) measurement."""

from __future__ import annotations

import numpy as np

from app.pipeline.emergence import compute_emergence


def test_no_previous_run_yields_undefined_emergence():
    current = {0: np.array([1.0, 0.0]), 1: np.array([0.0, 1.0])}
    result = compute_emergence(current, previous_centroids=[])
    assert result == {0: None, 1: None}


def test_continuation_is_low_novelty_and_new_topic_is_high():
    previous = [np.array([1.0, 0.0], dtype=np.float32)]
    current = {
        0: np.array([1.0, 0.0], dtype=np.float32),  # identical -> continuation
        1: np.array([0.0, 1.0], dtype=np.float32),  # orthogonal -> novel
    }
    result = compute_emergence(current, previous)
    assert result[0] < 0.05
    assert result[1] > 0.95


def test_emergence_is_bounded_to_unit_interval():
    previous = [np.array([1.0, 0.0]), np.array([-1.0, 0.0])]
    current = {0: np.array([0.0, 1.0])}
    score = compute_emergence(current, previous)[0]
    assert 0.0 <= score <= 1.0
