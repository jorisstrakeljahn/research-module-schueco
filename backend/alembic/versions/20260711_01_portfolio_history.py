"""Portfolio history, cumulative corpus and immutable Schüco baseline.

Revision ID: 20260711_01
Revises:
"""

from sqlalchemy import Column, inspect, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.sqltypes import Boolean, DateTime, Float, Integer, String

from alembic import op
from app.baseline import BASELINE_KEY, BASELINE_ROWS, BASELINE_TREND_IDS
from app.models import SQLModel

revision = "20260711_01"
down_revision = None
branch_labels = None
depends_on = None

def _add_column(table: str, column: Column) -> None:
    bind = op.get_bind()
    if column.name not in {item["name"] for item in inspect(bind).get_columns(table)}:
        op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    # This repository historically used SQLModel.create_all. Keeping the first
    # revision additive lets it upgrade both a demo.sql copy and a fresh database.
    SQLModel.metadata.create_all(bind)

    _add_column("document", Column("doi", String(), nullable=True))
    _add_column("document", Column("canonical_url", String(), nullable=True))
    _add_column("document", Column("content_hash", String(), nullable=True))
    _add_column("document", Column("normalized_identity", String(), nullable=True))
    _add_column("document", Column("duplicate_of_id", Integer(), nullable=True))
    _add_column("document", Column("near_duplicate_of_id", Integer(), nullable=True))
    _add_column(
        "document",
        Column("corpus_approved", Boolean(), nullable=False, server_default="false"),
    )
    _add_column("run", Column("corpus_hash", String(), nullable=True))
    _add_column("run", Column("corpus_cutoff", DateTime(timezone=True), nullable=True))
    _add_column("run", Column("component_manifest", JSONB(), nullable=True))
    _add_column("run", Column("prompt_manifest", JSONB(), nullable=True))
    _add_column("run", Column("git_revision", String(), nullable=True))
    _add_column("run", Column("embedder_revision", String(), nullable=True))
    _add_column("run", Column("topic_model_revision", String(), nullable=True))
    _add_column(
        "run", Column("random_seed", Integer(), nullable=False, server_default="42")
    )
    _add_column("run", Column("classifier", String(), nullable=True))
    _add_column("run", Column("usage_metrics", JSONB(), nullable=True))
    _add_column(
        "topic_timepoint",
        Column("prevalence", Float(), nullable=False, server_default="0"),
    )

    # create_all cannot add indexes/constraints to the historical tables.
    for name, table, cols, unique in (
        ("ix_document_doi", "document", ["doi"], True),
        ("ix_document_canonical_url", "document", ["canonical_url"], True),
        ("ix_document_content_hash", "document", ["content_hash"], True),
        ("ix_document_normalized_identity", "document", ["normalized_identity"], True),
        ("ix_document_corpus_approved", "document", ["corpus_approved"], False),
        ("ix_run_corpus_hash", "run", ["corpus_hash"], False),
    ):
        if name not in {item["name"] for item in inspect(bind).get_indexes(table)}:
            op.create_index(name, table, cols, unique=unique)
    if "uq_document_source_external_approved" not in {
        item["name"] for item in inspect(bind).get_indexes("document")
    }:
        op.create_index(
            "uq_document_source_external_approved",
            "document",
            ["source_id", "external_id"],
            unique=True,
            postgresql_where=text("corpus_approved AND external_id IS NOT NULL"),
        )

    _seed_legacy_run_7(bind)
    _protect_baseline(bind)


def _seed_legacy_run_7(bind) -> None:
    if not bind.execute(text("SELECT 1 FROM run WHERE id = 7")).first():
        return

    # Historical documents without trustworthy run membership must not silently
    # enter a new cumulative BERTopic corpus. Documents referenced by an explicit
    # run_document snapshot are post-migration evidence and remain approved when a
    # newer demo snapshot is imported and this idempotent migration is replayed.
    bind.execute(
        text(
            """
            UPDATE document
            SET corpus_approved = false
            WHERE id NOT IN (SELECT document_id FROM run_document)
            """
        )
    )
    bind.execute(
        text(
            """
            INSERT INTO baseline_snapshot (key, title, source, source_run_id, created_at)
            VALUES (:key, 'Schüco Tabelle 3 (2026)', 'accepted-report-table-3', 7, now())
            ON CONFLICT (key) DO NOTHING
            """
        ),
        {"key": BASELINE_KEY},
    )
    active_ids = ",".join(str(value) for value in BASELINE_TREND_IDS)
    bind.execute(
        text(
            f"""
            INSERT INTO canonical_trend (
                id, status, title, summary, maturity, pestel, category, impact,
                urgency, uncertainty, radar_stage, first_run_id, last_run_id,
                created_at, updated_at
            )
            SELECT
                'legacy-run-7-trend-' || t.id,
                CASE WHEN t.id IN ({active_ids}) THEN 'active' ELSE 'review' END,
                t.title, t.summary, t.maturity, a.pestel, a.category, a.impact,
                a.urgency, a.uncertainty, a.radar_stage, 7, 7, now(), now()
            FROM trend t
            LEFT JOIN trend_assessment a ON a.trend_id = t.id
            WHERE t.run_id = 7
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    bind.execute(
        text(
            f"""
            INSERT INTO trend_occurrence (
                canonical_trend_id, trend_id, run_id, change_type, changed_fields,
                created_at
            )
            SELECT
                'legacy-run-7-trend-' || t.id, t.id, 7,
                CASE WHEN t.id IN ({active_ids}) THEN 'unchanged' ELSE 'review' END,
                '[]'::jsonb, now()
            FROM trend t
            WHERE t.run_id = 7
            ON CONFLICT (trend_id) DO NOTHING
            """
        )
    )
    positions = " UNION ALL ".join(
        "SELECT "
        f"{position} AS position, {trend_id} AS trend_id, "
        f"'{title.replace(chr(39), chr(39) * 2)}'::varchar AS title, "
        f"{relevance}::float AS relevance, '{novelty}'::varchar AS novelty, "
        f"{traceability}::float AS traceability"
        for position, (
            trend_id,
            title,
            relevance,
            novelty,
            traceability,
        ) in enumerate(BASELINE_ROWS, 1)
    )
    bind.execute(
        text(
            f"""
            INSERT INTO baseline_trend (
                snapshot_key, position, legacy_trend_id, canonical_trend_id,
                title, relevance, novelty, traceability, payload
            )
            SELECT
                :key, ordering.position, t.id, 'legacy-run-7-trend-' || t.id,
                ordering.title, ordering.relevance, ordering.novelty,
                ordering.traceability,
                jsonb_build_object(
                    'machine_title', t.title, 'summary', t.summary, 'maturity', t.maturity,
                    'evidence', t.evidence, 'assessment', to_jsonb(a)
                )
            FROM ({positions}) ordering
            JOIN trend t ON t.id = ordering.trend_id AND t.run_id = 7
            LEFT JOIN trend_assessment a ON a.trend_id = t.id
            ON CONFLICT (snapshot_key, legacy_trend_id) DO NOTHING
            """
        ),
        {"key": BASELINE_KEY},
    )


def _protect_baseline(bind) -> None:
    bind.execute(
        text(
            """
            CREATE OR REPLACE FUNCTION reject_baseline_mutation()
            RETURNS trigger AS $$
            BEGIN
              RAISE EXCEPTION 'immutable records cannot be changed';
            END;
            $$ LANGUAGE plpgsql;
            DROP TRIGGER IF EXISTS baseline_snapshot_immutable ON baseline_snapshot;
            CREATE TRIGGER baseline_snapshot_immutable
              BEFORE UPDATE OR DELETE ON baseline_snapshot
              FOR EACH ROW EXECUTE FUNCTION reject_baseline_mutation();
            DROP TRIGGER IF EXISTS baseline_trend_immutable ON baseline_trend;
            CREATE TRIGGER baseline_trend_immutable
              BEFORE UPDATE OR DELETE ON baseline_trend
              FOR EACH ROW EXECUTE FUNCTION reject_baseline_mutation();
            DROP TRIGGER IF EXISTS trend_decision_immutable ON trend_decision;
            CREATE TRIGGER trend_decision_immutable
              BEFORE UPDATE OR DELETE ON trend_decision
              FOR EACH ROW EXECUTE FUNCTION reject_baseline_mutation();
            """
        )
    )


def downgrade() -> None:
    # Historical baseline deletion is intentionally unsupported.
    raise RuntimeError("Portfolio-history migration is irreversible by design")
