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


# Lightweight, idempotent column additions for tables that predate a model change.
# The project intentionally uses create_all instead of a migration tool (ADR-16);
# create_all does not ALTER existing tables, so additive columns are applied here.
_ADDITIVE_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("topic", "region", "VARCHAR"),
    ("topic", "country", "VARCHAR"),
    ("run", "error", "VARCHAR"),
)


def init_db() -> None:
    """Enable the pgvector extension, create all tables, apply additive columns."""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    SQLModel.metadata.create_all(engine)
    with engine.connect() as conn:
        for table, column, coltype in _ADDITIVE_COLUMNS:
            conn.execute(
                text(
                    f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS '
                    f'"{column}" {coltype}'
                )
            )
        conn.commit()
    _check_embedding_dimension(engine)


def _check_embedding_dimension(engine) -> None:
    """Fail fast if the live ``chunk.embedding`` column dimension drifted from
    ``EMBEDDING_DIM``. ``create_all`` never alters existing columns, so changing the
    embedder without recreating the DB would otherwise fail late with a cryptic error.

    For pgvector columns ``atttypmod`` holds the dimension directly (no offset).
    """
    expected = get_settings().embedding_dim
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT atttypmod FROM pg_attribute "
                "WHERE attrelid = 'chunk'::regclass AND attname = 'embedding'"
            )
        ).first()
    if row and row[0] != -1 and row[0] != expected:
        raise RuntimeError(
            f"Embedding dimension mismatch: database column chunk.embedding is "
            f"vector({row[0]}), but EMBEDDING_DIM={expected}. Either set "
            f"EMBEDDING_DIM={row[0]} or recreate the database (data loss!) after "
            f"changing the embedder."
        )


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a database session."""
    with Session(get_engine()) as session:
        yield session
