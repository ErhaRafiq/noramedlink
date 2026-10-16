"""symptom checker sessions (Module 7)

Additive and guarded: one new table, symptom_sessions. Nothing existing is changed.

Revision ID: 0016
Revises: 0015
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("symptom_sessions"):
        return
    op.create_table(
        "symptom_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("symptom_text", sa.Text(), nullable=False),
        sa.Column("red_flag", sa.Boolean(), nullable=False),
        sa.Column("red_flags", sa.String(200), server_default="", nullable=False),
        sa.Column("specialty", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_symptom_sessions_id", "symptom_sessions", ["id"])
    op.create_index("ix_symptom_sessions_user_id", "symptom_sessions", ["user_id"])
    op.create_index("ix_symptom_sessions_created_at", "symptom_sessions", ["created_at"])


def downgrade() -> None:
    # Sessions are records of real use: refuse while any exist.
    bind = op.get_bind()
    if sa.inspect(bind).has_table("symptom_sessions"):
        if bind.execute(sa.text("SELECT COUNT(*) FROM symptom_sessions")).scalar():
            raise RuntimeError("0016 cannot be downgraded: symptom sessions are recorded.")
        op.drop_table("symptom_sessions")
