"""Separate occurrence changes from the review workflow.

Revision ID: 20260713_01
Revises: 20260711_02
"""

from sqlalchemy import Column, inspect, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.sqltypes import Integer, String

from alembic import op

revision = "20260713_01"
down_revision = "20260711_02"
branch_labels = None
depends_on = None


def _add_column(column: Column) -> bool:
    bind = op.get_bind()
    names = {item["name"] for item in inspect(bind).get_columns("trend_occurrence")}
    if column.name not in names:
        op.add_column("trend_occurrence", column)
        return True
    return False


def upgrade() -> None:
    op.alter_column(
        "trend_occurrence",
        "canonical_trend_id",
        existing_type=String(),
        nullable=True,
    )
    added_review_status = _add_column(
        Column(
            "review_status",
            String(),
            nullable=False,
            server_default="not_required",
        )
    )
    _add_column(Column("review_reasons", JSONB(), nullable=True))
    _add_column(
        Column("evidence_added_count", Integer(), nullable=False, server_default="0")
    )
    _add_column(
        Column("evidence_removed_count", Integer(), nullable=False, server_default="0")
    )

    bind = op.get_bind()
    # Backfill only legacy rows. When the column already existed (e.g. seed-demo
    # restores a dump in the current format), the data is authoritative and must
    # not be rewritten.
    if not added_review_status:
        return
    bind.execute(
        text(
            """
            UPDATE trend_occurrence
            SET
              review_status = CASE
                WHEN change_type = 'review' THEN 'pending'
                WHEN change_type = 'new' THEN 'approved'
                ELSE 'not_required'
              END,
              review_reasons = CASE
                WHEN change_type = 'review' THEN jsonb_build_array(
                  jsonb_build_object(
                    'code', COALESCE(review_reason, 'legacy_review'),
                    'kind', 'identity'
                  )
                )
                ELSE NULL
              END,
              change_type = CASE
                WHEN change_type = 'review' THEN 'classification_changed'
                WHEN change_type = 'updated' AND changed_fields = '["summary"]'::jsonb
                  THEN 'content_changed'
                WHEN change_type = 'updated' THEN 'classification_changed'
                ELSE change_type
              END
            """
        )
    )
    indexes = {item["name"] for item in inspect(bind).get_indexes("trend_occurrence")}
    if "ix_trend_occurrence_review_status" not in indexes:
        op.create_index(
            "ix_trend_occurrence_review_status",
            "trend_occurrence",
            ["review_status"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        text(
            """
            UPDATE trend_occurrence
            SET change_type = CASE
              WHEN review_status = 'pending' THEN 'review'
              WHEN change_type IN ('classification_changed', 'content_changed',
                                   'evidence_only') THEN 'updated'
              ELSE change_type
            END
            """
        )
    )
    indexes = {item["name"] for item in inspect(bind).get_indexes("trend_occurrence")}
    if "ix_trend_occurrence_review_status" in indexes:
        op.drop_index(
            "ix_trend_occurrence_review_status", table_name="trend_occurrence"
        )
    for name in (
        "evidence_removed_count",
        "evidence_added_count",
        "review_reasons",
        "review_status",
    ):
        if name in {
            item["name"] for item in inspect(bind).get_columns("trend_occurrence")
        }:
            op.drop_column("trend_occurrence", name)
    if not bind.execute(
        text(
            "SELECT 1 FROM trend_occurrence "
            "WHERE canonical_trend_id IS NULL LIMIT 1"
        )
    ).first():
        op.alter_column(
            "trend_occurrence",
            "canonical_trend_id",
            existing_type=String(),
            nullable=False,
        )
