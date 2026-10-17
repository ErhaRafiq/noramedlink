"""notifications: where each one leads, when it was read, and a key so an event is told once

Additive and guarded: three nullable columns on notifications (link, read_at, dedupe_key with a unique
constraint) and an index for the unread count. Existing notifications keep working: one without a link
is opened through the page its kind belongs to.

Revision ID: 0020
Revises: 0019
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {c["name"] for c in inspector.get_columns("notifications")}
    if "link" not in existing:
        op.add_column("notifications", sa.Column("link", sa.String(200), nullable=True))
    if "read_at" not in existing:
        op.add_column("notifications", sa.Column("read_at", sa.DateTime(timezone=True), nullable=True))
    if "dedupe_key" not in existing:
        op.add_column("notifications", sa.Column("dedupe_key", sa.String(120), nullable=True))
    if "notifications_dedupe_key_key" not in {u["name"] for u in inspector.get_unique_constraints("notifications")}:
        op.create_unique_constraint("notifications_dedupe_key_key", "notifications", ["dedupe_key"])
    if "notifications_user_status_idx" not in {i["name"] for i in inspector.get_indexes("notifications")}:
        op.create_index("notifications_user_status_idx", "notifications", ["user_id", "status"])


def downgrade() -> None:
    # What a person was told is a record: refuse while any notification carries the new fields.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("notifications")}
    if "link" in existing and bind.execute(
        sa.text("SELECT COUNT(*) FROM notifications WHERE link IS NOT NULL OR dedupe_key IS NOT NULL OR read_at IS NOT NULL")
    ).scalar():
        raise RuntimeError("0020 cannot be downgraded: notifications use the new fields.")
    if "notifications_user_status_idx" in {i["name"] for i in inspector.get_indexes("notifications")}:
        op.drop_index("notifications_user_status_idx", table_name="notifications")
    if "notifications_dedupe_key_key" in {u["name"] for u in inspector.get_unique_constraints("notifications")}:
        op.drop_constraint("notifications_dedupe_key_key", "notifications", type_="unique")
    for name in ("dedupe_key", "read_at", "link"):
        if name in existing:
            op.drop_column("notifications", name)
