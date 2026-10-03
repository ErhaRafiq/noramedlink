"""additive schema alignment: legacy compatibility columns, unique grant pair, Prisma indexes

Everything here is additive and guarded, so it is safe on any database the project
has produced so far (fresh baseline, FastAPI create_all, or Prisma migrations):

1. Columns that database.ensure_schema_compatibility() used to add at startup, for
   databases created before those columns existed in the models.
2. The (doctor_id, patient_id) unique constraint on patient_dashboard_access that the
   Prisma schema declares and the OTP unlock upsert relies on.
3. Indexes declared by the Prisma schema that FastAPI-created databases were missing.

Revision ID: 0002
Revises: 0001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# table -> [(column, type, server_default)]
LEGACY_COLUMNS = {
    "users": [("is_active", sa.Boolean(), sa.true())],
    "signup_otps": [("payload_json", sa.JSON(), sa.text("'{}'"))],
    "patient_reports": [
        ("extracted_entities", sa.JSON(), sa.text("'[]'")),
        ("rule_warnings", sa.JSON(), sa.text("'[]'")),
        ("validation_status", sa.String(30), sa.text("'SAFE'")),
        ("validation_results", sa.JSON(), sa.text("'{}'")),
        ("clinical_summary_json", sa.JSON(), sa.text("'{}'")),
        ("llm_self_check", sa.JSON(), sa.text("'{}'")),
        ("summary_source", sa.String(80), sa.text("'rule_based'")),
    ],
}

GRANT_UNIQUE = "patient_dashboard_access_doctor_id_patient_id_key"

# name -> (table, columns); names match the Prisma migrations.
PRISMA_INDEXES = {
    "vitals_user_id_created_at_idx": ("vitals", ["user_id", "created_at"]),
    "reminders_user_id_due_at_idx": ("reminders", ["user_id", "due_at"]),
    "medical_documents_user_id_created_at_idx": ("medical_documents", ["user_id", "created_at"]),
    "medical_ai_analyses_user_id_created_at_idx": ("medical_ai_analyses", ["user_id", "created_at"]),
    "health_risk_predictions_patient_id_created_at_idx": ("health_risk_predictions", ["patient_id", "created_at"]),
    "health_tips_patient_id_created_at_idx": ("health_tips", ["patient_id", "created_at"]),
    "doctor_summaries_patient_id_generated_at_idx": ("doctor_summaries", ["patient_id", "generated_at"]),
    "notifications_user_id_created_at_idx": ("notifications", ["user_id", "created_at"]),
    "notifications_reminder_id_idx": ("notifications", ["reminder_id"]),
    "patient_reports_patient_id_upload_date_idx": ("patient_reports", ["patient_id", "upload_date"]),
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. Legacy compatibility columns.
    for table, columns in LEGACY_COLUMNS.items():
        existing = {c["name"] for c in inspector.get_columns(table)}
        for name, type_, default in columns:
            if name not in existing:
                op.add_column(table, sa.Column(name, type_, nullable=False, server_default=default))
    analysis_columns = {c["name"] for c in inspector.get_columns("medical_ai_analyses")}
    if "patient_report_id" not in analysis_columns:
        op.add_column("medical_ai_analyses", sa.Column("patient_report_id", sa.Integer(), nullable=True))

    # 2. Unique (doctor_id, patient_id) on dashboard access grants, unless any unique
    #    constraint or unique index on that pair already exists.
    pair = {"doctor_id", "patient_id"}
    has_unique = any(set(u["column_names"]) == pair for u in inspector.get_unique_constraints("patient_dashboard_access"))
    has_unique = has_unique or any(
        ix["unique"] and set(ix["column_names"]) == pair for ix in inspector.get_indexes("patient_dashboard_access")
    )
    if not has_unique:
        duplicates = bind.execute(
            sa.text(
                "SELECT count(*) FROM (SELECT doctor_id, patient_id FROM patient_dashboard_access "
                "GROUP BY doctor_id, patient_id HAVING count(*) > 1) d"
            )
        ).scalar()
        if duplicates:
            raise RuntimeError(
                f"patient_dashboard_access has {duplicates} duplicate (doctor_id, patient_id) pairs; "
                "resolve them before adding the unique constraint."
            )
        with op.batch_alter_table("patient_dashboard_access") as batch:
            batch.create_unique_constraint(GRANT_UNIQUE, ["doctor_id", "patient_id"])

    # 3. Prisma-declared indexes.
    for name, (table, columns) in PRISMA_INDEXES.items():
        if name not in {ix["name"] for ix in inspector.get_indexes(table)}:
            op.create_index(name, table, columns)


def downgrade() -> None:
    for name, (table, _columns) in PRISMA_INDEXES.items():
        op.drop_index(name, table_name=table)
    # Columns and the unique constraint are kept: removing them could lose data or break
    # the OTP unlock flow, and they may have existed before this migration.
