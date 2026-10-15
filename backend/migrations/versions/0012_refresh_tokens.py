"""add refresh_tokens (rotating refresh tokens for sign-in sessions)

Additive and guarded: one new table; nothing existing is changed. Rows are sessions, not medical
data, so the downgrade may drop them (everyone is signed out).

Revision ID: 0012
Revises: 0011
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("refresh_tokens"):
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("family_id", sa.String(32), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    existing = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("refresh_tokens")}
    for name, columns in (("refresh_tokens_user_id_idx", ["user_id"]), ("refresh_tokens_family_idx", ["family_id"])):
        if name not in existing:
            op.create_index(name, "refresh_tokens", columns)


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("refresh_tokens"):
        op.drop_table("refresh_tokens")
