"""email: one-time tokens, the outbox, and the reminder preference

Additive and guarded: two new tables (auth_tokens, email_outbox) and one column on users
(email_reminders, true for everyone). Existing users keep is_email_verified as it is.

Revision ID: 0019
Revises: 0018
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "email_reminders" not in {c["name"] for c in inspector.get_columns("users")}:
        op.add_column("users", sa.Column("email_reminders", sa.Boolean(), server_default=sa.true(), nullable=False))
    if not inspector.has_table("auth_tokens"):
        op.create_table(
            "auth_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("purpose", sa.String(20), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_auth_tokens_token_hash", "auth_tokens", ["token_hash"])
        op.create_index("auth_tokens_user_purpose_idx", "auth_tokens", ["user_id", "purpose", "created_at"])
    if not inspector.has_table("email_outbox"):
        op.create_table(
            "email_outbox",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("to_address", sa.String(255), nullable=False),
            sa.Column("kind", sa.String(40), nullable=False),
            sa.Column("context", sa.JSON(), nullable=True),
            sa.Column("dedupe_key", sa.String(160), nullable=False, unique=True),
            sa.Column("appointment_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(12), server_default="pending", nullable=False),
            sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
            sa.Column("send_after", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("provider_id", sa.String(80), nullable=True),
            sa.Column("last_error", sa.String(200), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_email_outbox_user_id", "email_outbox", ["user_id"])
        op.create_index("ix_email_outbox_appointment_id", "email_outbox", ["appointment_id"])
        op.create_index("email_outbox_due_idx", "email_outbox", ["status", "send_after"])


def downgrade() -> None:
    # A sent email is a record of what a person was told (and a one-time token a security record): refuse
    # while either table has rows. The reminder preference column is dropped with it.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in ("email_outbox", "auth_tokens"):
        if inspector.has_table(table) and bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar():
            raise RuntimeError(f"0019 cannot be downgraded: {table} has records.")
    for table in ("email_outbox", "auth_tokens"):
        if inspector.has_table(table):
            op.drop_table(table)
    if "email_reminders" in {c["name"] for c in inspector.get_columns("users")}:
        op.drop_column("users", "email_reminders")
