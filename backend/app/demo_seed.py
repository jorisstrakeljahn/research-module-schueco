"""Load the committed demo dataset into a fresh local database."""

from __future__ import annotations

import subprocess
from pathlib import Path

from sqlalchemy import text
from sqlmodel import SQLModel

from app.db import get_engine, init_db

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_SQL = REPO_ROOT / "data" / "demo.sql"
DOCKER_DB_CONTAINER = "trendscout-db"


def demo_sql_path() -> Path:
    return DEMO_SQL


def seed_demo_database() -> None:
    """Replace local DB contents with the committed demo snapshot."""
    sql_path = demo_sql_path()
    if not sql_path.is_file():
        raise FileNotFoundError(
            f"Demo snapshot not found at {sql_path}. "
            "Run from the repository root after cloning."
        )

    init_db()
    _truncate_all_tables()
    _import_sql_file(sql_path)


def _truncate_all_tables() -> None:
    table_names = ", ".join(t.name for t in reversed(SQLModel.metadata.sorted_tables))
    with get_engine().connect() as conn:
        conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
        conn.commit()


def _docker_db_running() -> bool:
    try:
        proc = subprocess.run(
            [
                "docker",
                "inspect",
                "-f",
                "{{.State.Running}}",
                DOCKER_DB_CONTAINER,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _import_sql_file(sql_path: Path) -> None:
    if _docker_db_running():
        proc = subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                DOCKER_DB_CONTAINER,
                "psql",
                "-v",
                "ON_ERROR_STOP=1",
                "-U",
                "trendscout",
                "-d",
                "trendscout",
            ],
            stdin=sql_path.open("rb"),
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            detail = proc.stderr.decode() or proc.stdout.decode()
            raise RuntimeError(f"Demo import via Docker failed:\n{detail}")
        return

    proc = subprocess.run(
        [
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "postgresql://trendscout:trendscout@localhost:5433/trendscout",
        ],
        stdin=sql_path.open("rb"),
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.decode() or proc.stdout.decode()
        raise RuntimeError(
            "Demo import failed. Start Postgres with "
            "`docker compose up -d db` or install `psql` locally.\n"
            f"{detail}"
        )
