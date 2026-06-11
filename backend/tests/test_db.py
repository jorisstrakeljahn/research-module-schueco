"""Tests for database initialization and the embedding-dimension safety check."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.db as db
from tests.conftest import requires_db


@requires_db
def test_init_db_is_idempotent_on_matching_dim():
    # The default EMBEDDING_DIM (384) matches the live column, so this must not raise.
    db.init_db()


@requires_db
def test_init_db_raises_on_dimension_mismatch(monkeypatch):
    real_url = db.get_settings().database_url
    monkeypatch.setattr(
        db,
        "get_settings",
        lambda: SimpleNamespace(embedding_dim=999, database_url=real_url),
    )
    with pytest.raises(RuntimeError, match="dimension mismatch"):
        db.init_db()
