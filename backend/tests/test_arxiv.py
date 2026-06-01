"""Tests for the arXiv Atom parser (offline, no network)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.ingestion.arxiv import parse_atom

SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2301.00001v1</id>
    <published>2023-01-02T10:00:00Z</published>
    <title>Adaptive Facades for Energy Efficient Buildings</title>
    <summary>We study adaptive building envelopes that reduce energy demand.</summary>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2105.12345v2</id>
    <published>2021-05-20T08:30:00Z</published>
    <title>Building Integrated Photovoltaics Review</title>
    <summary>A survey of BIPV technologies for facades.</summary>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/empty</id>
    <published>2020-01-01T00:00:00Z</published>
    <title></title>
    <summary>no title should be skipped</summary>
  </entry>
</feed>"""


def test_parse_atom_maps_entries() -> None:
    docs = parse_atom(SAMPLE_FEED)
    assert len(docs) == 2  # the empty-title entry is skipped

    first = docs[0]
    assert first.title == "Adaptive Facades for Energy Efficient Buildings"
    assert "adaptive building envelopes" in first.text
    assert first.url == "http://arxiv.org/abs/2301.00001v1"
    assert first.source_name == "arXiv"
    assert first.source_type == "preprint"
    assert first.published_at == datetime(2023, 1, 2, 10, 0, tzinfo=UTC)


def test_parse_atom_handles_empty_feed() -> None:
    empty = '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
    assert parse_atom(empty) == []
