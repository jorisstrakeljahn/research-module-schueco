"""Manual newsfeed ordering: position column on canonical_trend.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _column_names() -> set[str]:
    bind = op.get_bind()
    return {item["name"] for item in inspect(bind).get_columns("canonical_trend")}


def upgrade() -> None:
    # Idempotent: seed-demo re-runs all migrations on a metadata-created schema.
    if "position" not in _column_names():
        op.add_column(
            "canonical_trend",
            sa.Column("position", sa.Float(), nullable=True),
        )


def downgrade() -> None:
    if "position" in _column_names():
        op.drop_column("canonical_trend", "position")
