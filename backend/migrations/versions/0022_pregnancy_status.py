"""pregnancy status on the patient profile

Additive and guarded: four nullable columns on patient_profiles (status, when it was set, by which role and
which user). Null means "not recorded"; nothing is filled in for existing patients.

Revision ID: 0022
Revises: 0021
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = ("pregnancy_status", "pregnancy_status_set_at", "pregnancy_status_set_by_role", "pregnancy_status_set_by_id")


def upgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("patient_profiles")}
    if "pregnancy_status" not in existing:
        op.add_column("patient_profiles", sa.Column("pregnancy_status", sa.String(20), nullable=True))
    if "pregnancy_status_set_at" not in existing:
        op.add_column("patient_profiles", sa.Column("pregnancy_status_set_at", sa.DateTime(timezone=True), nullable=True))
    if "pregnancy_status_set_by_role" not in existing:
        op.add_column("patient_profiles", sa.Column("pregnancy_status_set_by_role", sa.String(20), nullable=True))
    if "pregnancy_status_set_by_id" not in existing:
        op.add_column(
            "patient_profiles",
            sa.Column("pregnancy_status_set_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        )


def downgrade() -> None:
    # The columns hold patients' records: refuse while any status is recorded.
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns("patient_profiles")}
    if "pregnancy_status" in existing and bind.execute(
        sa.text("SELECT COUNT(*) FROM patient_profiles WHERE pregnancy_status IS NOT NULL")
    ).scalar():
        raise RuntimeError("0022 cannot be downgraded: pregnancy statuses are recorded.")
    for column in reversed(COLUMNS):
        if column in existing:
            op.drop_column("patient_profiles", column)
