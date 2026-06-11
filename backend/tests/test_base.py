"""Tests for the shared ingestion helpers in app.ingestion.base."""

from __future__ import annotations

from datetime import UTC, datetime

from app.ingestion.base import parse_date


def test_parse_date_full_iso_timestamp() -> None:
    assert parse_date("2023-01-02T10:00:00Z") == datetime(
        2023, 1, 2, 10, 0, tzinfo=UTC
    )


def test_parse_date_date_only_is_utc_normalised() -> None:
    parsed = parse_date("2024-05-10")
    assert parsed == datetime(2024, 5, 10, tzinfo=UTC)
    assert parsed.tzinfo is not None


def test_parse_date_garbage_and_empty_return_none() -> None:
    assert parse_date("not-a-date") is None
    assert parse_date(None) is None
    assert parse_date("") is None
