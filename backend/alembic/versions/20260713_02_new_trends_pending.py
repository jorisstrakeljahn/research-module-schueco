"""New trends always require a human review decision.

Revision ID: 20260713_02
Revises: 20260713_01
"""

from sqlalchemy import text

from alembic import op

revision = "20260713_02"
down_revision = "20260713_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(
        text(
            """
            UPDATE trend_occurrence
            SET
              review_status = 'pending',
              review_reasons = jsonb_build_array(
                jsonb_build_object('code', 'new_trend', 'kind', 'classification')
              ),
              review_reason = 'new_trend'
            WHERE change_type = 'new'
              AND review_status = 'approved'
              AND NOT EXISTS (
                SELECT 1 FROM trend_decision
                WHERE trend_decision.occurrence_id = trend_occurrence.id
              )
            """
        )
    )


def downgrade() -> None:
    op.get_bind().execute(
        text(
            """
            UPDATE trend_occurrence
            SET
              review_status = 'approved',
              review_reasons = NULL,
              review_reason = NULL
            WHERE change_type = 'new'
              AND review_status = 'pending'
              AND review_reason = 'new_trend'
            """
        )
    )
