"""Tests for the OpenAlex connector (parsing + HTTP, fully mocked)."""

from __future__ import annotations

import httpx
import respx

from app.ingestion.openalex import (
    OPENALEX_WORKS_URL,
    OpenAlexConnector,
    reconstruct_abstract,
    work_to_document,
)


def test_reconstruct_abstract_orders_words():
    inverted = {"Adaptive": [0], "facade": [1], "systems": [2]}
    assert reconstruct_abstract(inverted) == "Adaptive facade systems"


def test_reconstruct_abstract_handles_empty():
    assert reconstruct_abstract(None) == ""
    assert reconstruct_abstract({}) == ""


def test_work_to_document_maps_fields():
    work = {
        "id": "https://openalex.org/W123",
        "title": "Building integrated photovoltaics",
        "publication_date": "2024-05-10",
        "language": "en",
        "abstract_inverted_index": {"BIPV": [0], "review": [1]},
    }
    doc = work_to_document(work)
    assert doc.external_id == "https://openalex.org/W123"
    assert doc.title == "Building integrated photovoltaics"
    assert "BIPV review" in doc.text
    assert doc.published_at.year == 2024 and doc.published_at.month == 5
    assert doc.source_type == "science"


def test_work_to_document_extracts_region_from_authorships():
    work = {
        "id": "https://openalex.org/W9",
        "title": "Facade research in China",
        "authorships": [
            {"institutions": [{"country_code": "CN"}]},
            {"institutions": [{"country_code": "CN"}, {"country_code": "DE"}]},
        ],
    }
    doc = work_to_document(work)
    assert doc.country == "CN"
    assert doc.region == "Asia"


def test_work_to_document_region_none_without_country():
    doc = work_to_document({"id": "x", "title": "No affiliation"})
    assert doc.country is None
    assert doc.region is None


@respx.mock
def test_fetch_calls_api_and_parses():
    payload = {
        "results": [
            {
                "id": "https://openalex.org/W1",
                "title": "Circular construction",
                "publication_date": "2023-01-01",
                "language": "en",
                "abstract_inverted_index": {"circular": [0], "economy": [1]},
            },
            {  # empty -> filtered out
                "id": "https://openalex.org/W2",
                "title": "",
                "publication_date": None,
                "abstract_inverted_index": None,
            },
        ]
    }
    route = respx.get(OPENALEX_WORKS_URL).mock(
        return_value=httpx.Response(200, json=payload)
    )
    connector = OpenAlexConnector()
    docs = connector.fetch("circular construction", limit=10)

    assert route.called
    assert len(docs) == 1
    assert docs[0].title == "Circular construction"
