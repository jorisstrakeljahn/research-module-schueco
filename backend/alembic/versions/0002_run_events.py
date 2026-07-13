"""Append-only live progress events for pipeline runs.

Revision ID: 0002
Revises: 0001
"""

from alembic import op
from app.models import RunEvent

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    RunEvent.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.drop_table("run_event")
