"""add patient_vitals (detailed daily vitals, Prisma model PatientVital)

Additive and guarded: the table is created only if it does not exist yet.

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("patient_vitals"):
        return
    op.create_table(
        "patient_vitals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("blood_pressure_systolic", sa.Integer(), nullable=False),
        sa.Column("blood_pressure_diastolic", sa.Integer(), nullable=False),
        sa.Column("heart_rate", sa.Integer(), nullable=False),
        sa.Column("spo2", sa.Integer(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("sugar_level", sa.Float(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("patient_vitals_patient_id_recorded_at_idx", "patient_vitals", ["patient_id", "recorded_at"])


def downgrade() -> None:
    # Dropping the table would delete recorded vitals; refuse instead.
    raise NotImplementedError("0003 cannot be downgraded without data loss.")
