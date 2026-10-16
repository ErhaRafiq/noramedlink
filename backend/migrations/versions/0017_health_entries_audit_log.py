"""structured health record entries and the audit log (Module 2)

Additive and guarded: two new tables, patient_health_entries and audit_logs. Nothing existing is changed.

Revision ID: 0017
Revises: 0016
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("patient_health_entries"):
        op.create_table(
            "patient_health_entries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("severity", sa.String(20), nullable=True),
            sa.Column("since", sa.Date(), nullable=True),
            sa.Column("status", sa.String(20), server_default="active", nullable=False),
            sa.Column("added_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("added_by_role", sa.String(20), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_patient_health_entries_id", "patient_health_entries", ["id"])
        op.create_index(
            "patient_health_entries_patient_kind_idx", "patient_health_entries", ["patient_id", "kind", "status"]
        )
    if not inspector.has_table("audit_logs"):
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("actor_role", sa.String(20), nullable=False),
            sa.Column("action", sa.String(60), nullable=False),
            sa.Column("target_type", sa.String(40), nullable=True),
            sa.Column("target_id", sa.Integer(), nullable=True),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("detail", sa.String(300), server_default="", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        for column in ("id", "actor_id", "action", "patient_id", "created_at"):
            op.create_index(f"ix_audit_logs_{column}", "audit_logs", [column])


def downgrade() -> None:
    # Both tables hold real records (the audit trail is meant to be kept): refuse while they have rows.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in ("audit_logs", "patient_health_entries"):
        if inspector.has_table(table) and bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar():
            raise RuntimeError(f"0017 cannot be downgraded: {table} has records.")
    for table in ("audit_logs", "patient_health_entries"):
        if inspector.has_table(table):
            op.drop_table(table)
