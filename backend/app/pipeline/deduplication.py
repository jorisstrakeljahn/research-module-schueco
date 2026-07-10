"""Global, database-backed document identity and duplicate detection."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlmodel import Session, select

from app.ingestion.base import RawDocument
from app.models import Document

_DOI_RE = re.compile(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.I)
_TRACKING_PARAMS = {"fbclid", "gclid", "ref", "source"}


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def content_fingerprint(title: str, text: str) -> str:
    payload = f"{normalize_text(title)}\n{normalize_text(text)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def extract_doi(raw: RawDocument) -> str | None:
    for value in (raw.external_id, raw.url, raw.text[:500]):
        match = _DOI_RE.search(value or "")
        if match:
            return match.group(1).rstrip(".,;)").casefold()
    return None


def canonicalize_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value.strip())
    if not parsed.netloc:
        return None
    query = urlencode(
        sorted(
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.casefold().startswith("utm_")
            and key.casefold() not in _TRACKING_PARAMS
        )
    )
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit(
        (parsed.scheme.casefold() or "https", parsed.netloc.casefold(), path, query, "")
    )


@dataclass(frozen=True)
class DocumentIdentity:
    doi: str | None
    canonical_url: str | None
    content_hash: str
    normalized_identity: str


def identity_for(raw: RawDocument, source_name: str) -> DocumentIdentity:
    doi = extract_doi(raw)
    url = canonicalize_url(raw.url)
    content_hash = content_fingerprint(raw.title, raw.text)
    if doi:
        identity = f"doi:{doi}"
    elif url:
        identity = f"url:{url}"
    elif raw.external_id:
        identity = f"source:{source_name.casefold()}:{raw.external_id.casefold()}"
    else:
        identity = f"sha256:{content_hash}"
    return DocumentIdentity(doi, url, content_hash, identity)


def find_exact_duplicate(
    session: Session,
    identity: DocumentIdentity,
    *,
    source_id: int | None = None,
    external_id: str | None = None,
) -> Document | None:
    checks = [Document.normalized_identity == identity.normalized_identity]
    if identity.doi:
        checks.append(Document.doi == identity.doi)
    if identity.canonical_url:
        checks.append(Document.canonical_url == identity.canonical_url)
    checks.append(Document.content_hash == identity.content_hash)
    if source_id is not None and external_id:
        checks.append(
            (Document.source_id == source_id) & (Document.external_id == external_id)
        )
    for condition in checks:
        found = session.exec(select(Document).where(condition)).first()
        if found:
            return found
    return None


def find_near_duplicate(
    session: Session, raw: RawDocument, *, threshold: float = 0.94
) -> Document | None:
    """Conservatively mark title-near-duplicates; never merge them automatically."""
    title = normalize_text(raw.title)
    if len(title) < 20:
        return None
    candidates = session.exec(
        select(Document).order_by(Document.id.desc()).limit(200)
    ).all()
    for candidate in candidates:
        if SequenceMatcher(None, title, normalize_text(candidate.title)).ratio() >= threshold:
            return candidate
    return None
