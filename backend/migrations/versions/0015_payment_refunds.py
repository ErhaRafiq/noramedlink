"""payment refunds: Stripe refund id and refund time

Additive and guarded: two nullable columns on payments. Nothing existing is changed.

Revision ID: 0015
Revises: 0014
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = [
    sa.Column("stripe_refund_id", sa.String(255), nullable=True),
    sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
]


def upgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("payments")}
    for column in COLUMNS:
        if column.name not in existing:
            op.add_column("payments", column)


def downgrade() -> None:
    # Refund records belong to real payments: refuse while any is recorded.
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns("payments")}
    if "stripe_refund_id" in existing and bind.execute(
        sa.text("SELECT COUNT(*) FROM payments WHERE stripe_refund_id IS NOT NULL OR refunded_at IS NOT NULL")
    ).scalar():
        raise RuntimeError("0015 cannot be downgraded: payments have refund records.")
    for name in ("refunded_at", "stripe_refund_id"):
        if name in existing:
            op.drop_column("payments", name)
