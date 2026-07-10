"""Stable materialization of cumulative run corpora."""

from __future__ import annotations

import hashlib
from datetime import datetime

from sqlmodel import Session, select

from app.models import Document, RunDocument


def materialize_corpus(
    session: Session,
    *,
    run_id: int,
    cutoff: datetime,
    new_document_ids: set[int],
) -> tuple[list[Document], str]:
    """Persist and return the approved corpus in a deterministic order."""
    documents = list(
        session.exec(
            select(Document)
            .where(
                Document.corpus_approved.is_(True),
                Document.duplicate_of_id.is_(None),
                Document.created_at <= cutoff,
            )
            .order_by(
                Document.published_at.asc().nulls_last(),
                Document.content_hash.asc().nulls_last(),
                Document.id.asc(),
            )
        ).all()
    )
    digest = hashlib.sha256()
    for position, document in enumerate(documents):
        stable_identity = document.content_hash or f"legacy-document:{document.id}"
        digest.update(stable_identity.encode("utf-8"))
        digest.update(b"\n")
        session.add(
            RunDocument(
                run_id=run_id,
                document_id=document.id,
                provenance="new" if document.id in new_document_ids else "carried_forward",
                position=position,
            )
        )
    session.flush()
    return documents, digest.hexdigest()
