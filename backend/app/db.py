"""Database engine, session and initialization helpers."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

# Import models so they are registered on SQLModel.metadata before create_all.
from app import models  # noqa: F401
from app.config import get_settings

_engine = None


def get_engine():
    """Return a lazily-created SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, echo=False)
    return _engine


def init_db() -> None:
    """Enable the pgvector extension and create all tables."""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a database session."""
    with Session(get_engine()) as session:
        yield session
