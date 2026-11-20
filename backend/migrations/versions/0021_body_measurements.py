"""dated body weight and height history (patient_body_measurements)

Additive and guarded: one new table. Nothing existing is changed or moved (patient_vitals.weight, an
unused column with no unit, is left as it is). The range checks mirror services/body_measurements.py.

Revision ID: 0021
Revises: 0020
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("patient_body_measurements"):
        return
    op.create_table(
        "patient_body_measurements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weight_kg", sa.Numeric(5, 2), nullable=True),
        sa.Column("height_cm", sa.Numeric(4, 1), nullable=True),
        sa.Column("measured_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("added_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("added_by_role", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("weight_kg IS NOT NULL OR height_cm IS NOT NULL", name="body_measurement_has_a_value"),
        sa.CheckConstraint("weight_kg IS NULL OR (weight_kg >= 2 AND weight_kg <= 350)", name="body_weight_range"),
        sa.CheckConstraint("height_cm IS NULL OR (height_cm >= 40 AND height_cm <= 250)", name="body_height_range"),
    )
    op.create_index("ix_patient_body_measurements_id", "patient_body_measurements", ["id"])
    op.create_index(
        "patient_body_measurements_patient_date_idx", "patient_body_measurements", ["patient_id", "measured_on"]
    )


def downgrade() -> None:
    # The table holds patients' records: refuse while it has rows.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("patient_body_measurements"):
        return
    if bind.execute(sa.text("SELECT COUNT(*) FROM patient_body_measurements")).scalar():
        raise RuntimeError("0021 cannot be downgraded: patient_body_measurements has records.")
    op.drop_table("patient_body_measurements")
