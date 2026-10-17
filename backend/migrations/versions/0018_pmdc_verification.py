"""PMDC verification flag and the result of the register check (doctor verification)

Additive and guarded: seven columns on doctor_profiles. Every existing doctor starts as not PMDC verified.
Nothing existing is changed, so an approved doctor stays approved and active.

Revision ID: 0018
Revises: 0017
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = [
    sa.Column("pmdc_verified", sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column("pmdc_outcome", sa.String(20), nullable=True),
    sa.Column("pmdc_checked_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("pmdc_register_name", sa.String(160), nullable=True),
    sa.Column("pmdc_register_status", sa.String(40), nullable=True),
    sa.Column("pmdc_checked_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    sa.Column("pmdc_note", sa.String(300), nullable=True),
]


def upgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("doctor_profiles")}
    for column in COLUMNS:
        if column.name not in existing:
            op.add_column("doctor_profiles", column)


def downgrade() -> None:
    # A recorded check or a manual decision is a real record: refuse while any exists.
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns("doctor_profiles")}
    if "pmdc_checked_at" in existing and bind.execute(
        sa.text("SELECT COUNT(*) FROM doctor_profiles WHERE pmdc_checked_at IS NOT NULL OR pmdc_verified")
    ).scalar():
        raise RuntimeError("0018 cannot be downgraded: doctors have PMDC check results.")
    for column in reversed(COLUMNS):
        if column.name in existing:
            op.drop_column("doctor_profiles", column.name)
