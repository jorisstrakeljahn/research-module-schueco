"""Database engine, session and initialization helpers."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from alembic.config import Config
from sqlalchemy import text
from sqlmodel import Session, create_engine

from alembic import command

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
    """Upgrade the database to the current Alembic revision."""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    backend_dir = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    command.upgrade(alembic_cfg, "head")
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
