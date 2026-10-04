"""add dashboard_otp_attempts (rate limiting and audit of OTP redemption attempts)

Additive and guarded.

Revision ID: 0007
Revises: 0006
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("dashboard_otp_attempts"):
        return
    op.create_table(
        "dashboard_otp_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("context", sa.String(20), nullable=False),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("dashboard_otp_attempts_actor_id_created_at_idx", "dashboard_otp_attempts", ["actor_id", "created_at"])


def downgrade() -> None:
    # Dropping the table would delete the audit trail; refuse instead.
    raise NotImplementedError("0007 cannot be downgraded without losing the attempt log.")
