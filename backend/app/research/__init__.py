"""Deep-research layer: seeds, query expansion, relevance gating and crawling.

This package implements *focused crawling* / *snowball sampling* (ADR-22): starting
from domain seed terms, it iteratively fetches documents from the configured sources,
filters them for relevance, and expands the query frontier with new terms derived from
what was found - bounded by a fixed number of rounds and a document budget so it stays
cheap and cannot run away.
"""
