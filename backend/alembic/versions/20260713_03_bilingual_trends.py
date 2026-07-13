"""Bilingual portfolio trends: translations JSONB on canonical_trend.

Revision ID: 20260713_03
Revises: 20260713_02
"""

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "20260713_03"
down_revision = "20260713_02"
branch_labels = None
depends_on = None


def _column_names() -> set[str]:
    bind = op.get_bind()
    return {item["name"] for item in inspect(bind).get_columns("canonical_trend")}


def upgrade() -> None:
    # Idempotent: seed-demo re-runs all migrations on a metadata-created schema.
    if "translations" not in _column_names():
        op.add_column(
            "canonical_trend",
            sa.Column("translations", JSONB(), nullable=True),
        )


def downgrade() -> None:
    if "translations" in _column_names():
        op.drop_column("canonical_trend", "translations")
