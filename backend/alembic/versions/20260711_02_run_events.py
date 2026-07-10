"""Append-only live progress events for pipeline runs.

Revision ID: 20260711_02
Revises: 20260711_01
"""

from alembic import op
from app.models import RunEvent

revision = "20260711_02"
down_revision = "20260711_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    RunEvent.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.drop_table("run_event")
