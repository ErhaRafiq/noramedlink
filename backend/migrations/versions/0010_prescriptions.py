"""add prescriptions, prescription_items and safety_overrides (MSCIE, Module 4)

Additive and guarded: new tables only; nothing existing is changed.

Revision ID: 0010
Revises: 0009
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("safety_overrides", "prescription_items", "prescriptions")


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("prescriptions"):
        op.create_table(
            "prescriptions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("doctor_name", sa.String(160), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("check_result", sa.JSON(), nullable=False),
            sa.Column("context_snapshot", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not inspector.has_table("prescription_items"):
        op.create_table(
            "prescription_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "prescription_id", sa.Integer(), sa.ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("medicine", sa.String(160), nullable=False),
            sa.Column("generic", sa.String(160), nullable=True),
            sa.Column("dose", sa.String(60), nullable=True),
            sa.Column("frequency", sa.String(60), nullable=True),
            sa.Column("duration", sa.String(60), nullable=True),
            sa.Column("instructions", sa.Text(), nullable=True),
            sa.Column("replaced_medicine", sa.String(160), nullable=True),
        )
    if not inspector.has_table("safety_overrides"):
        op.create_table(
            "safety_overrides",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "prescription_id", sa.Integer(), sa.ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("alert_id", sa.String(300), nullable=False),
            sa.Column("alert_severity", sa.String(20), nullable=False),
            sa.Column("alert_title", sa.String(300), nullable=False),
            sa.Column("justification", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    wanted = {
        "prescriptions": [
            ("ix_prescriptions_id", ["id"]),
            ("prescriptions_patient_id_created_at_idx", ["patient_id", "created_at"]),
        ],
        "prescription_items": [
            ("ix_prescription_items_id", ["id"]),
            ("ix_prescription_items_prescription_id", ["prescription_id"]),
        ],
        "safety_overrides": [
            ("ix_safety_overrides_id", ["id"]),
            ("ix_safety_overrides_prescription_id", ["prescription_id"]),
        ],
    }
    inspector = sa.inspect(op.get_bind())
    for table, indexes in wanted.items():
        existing = {index["name"] for index in inspector.get_indexes(table)}
        for name, columns in indexes:
            if name not in existing:
                op.create_index(name, table, columns)


def downgrade() -> None:
    # Prescriptions and override justifications are part of the medical record: refuse to drop any.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in TABLES:
        if inspector.has_table(table) and bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar():
            raise RuntimeError(f"0010 cannot be downgraded: {table} has rows (prescriptions are medical records).")
    for table in TABLES:
        if inspector.has_table(table):
            op.drop_table(table)
