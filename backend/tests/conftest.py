"""Shared pytest fixtures.

Tests run hermetically: they use a dedicated ``trendscout_test`` database and force the
deterministic *offline* pipeline components, independent of the developer's ``.env``
(which may point the app at OpenAI). This keeps tests free, fast and isolated from the
live demo data. The test database requires the docker-compose Postgres
(``docker compose up -d db``); if it is unreachable, database-backed tests are skipped.
"""

from __future__ import annotations

import os

# Force offline, deterministic settings BEFORE any app module imports them. Environment
# variables take precedence over the .env file in pydantic-settings.
os.environ["EMBEDDER"] = "hashing"
os.environ["TOPIC_MODEL"] = "simple"
os.environ["DESCRIBER"] = "template"
os.environ["EMBEDDING_DIM"] = "384"
os.environ["SOURCES"] = "openalex"
os.environ["EXPANDER"] = "none"
os.environ["RELEVANCE"] = "off"
os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://trendscout:trendscout@localhost:5433/trendscout_test"
)

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.db import get_engine, init_db  # noqa: E402

_TEST_DB = "trendscout_test"
_ADMIN_URL = "postgresql+psycopg://trendscout:trendscout@localhost:5433/trendscout"


def _ensure_test_database() -> bool:
    """Create the dedicated test database if it does not exist. Returns availability."""
    try:
        admin = create_engine(_ADMIN_URL, isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": _TEST_DB}
            ).first()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{_TEST_DB}"'))
        admin.dispose()
        return True
    except OperationalError:
        return False


def _database_available() -> bool:
    if not _ensure_test_database():
        return False
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False


requires_db = pytest.mark.skipif(
    not _database_available(),
    reason="Postgres not reachable (run: docker compose up -d db)",
)


@pytest.fixture(scope="session", autouse=True)
def _init_database() -> None:
    if _database_available():
        init_db()


@pytest.fixture
def session() -> Iterator[Session]:
    """Yield a session and truncate all tables afterwards for isolation."""
    engine = get_engine()
    with Session(engine) as s:
        yield s
    from sqlmodel import SQLModel

    table_names = ", ".join(t.name for t in reversed(SQLModel.metadata.sorted_tables))
    with engine.connect() as conn:
        conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
        conn.commit()
