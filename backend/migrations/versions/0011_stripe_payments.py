"""add consultation fees and Stripe Checkout fields (payments)

Additive and guarded: one nullable column on doctor_profiles, three columns on payments and a
new stripe_events table. Nothing existing is changed.

Revision ID: 0011
Revises: 0010
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PAYMENT_COLUMNS = [
    sa.Column("currency", sa.String(3), server_default="pkr", nullable=False),
    sa.Column("stripe_session_id", sa.String(255), nullable=True),
    sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
]


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "consultation_fee" not in {c["name"] for c in inspector.get_columns("doctor_profiles")}:
        op.add_column("doctor_profiles", sa.Column("consultation_fee", sa.Integer(), nullable=True))
    existing = {c["name"] for c in inspector.get_columns("payments")}
    for column in PAYMENT_COLUMNS:
        if column.name not in existing:
            op.add_column("payments", column)
    unique = {u["name"] for u in inspector.get_unique_constraints("payments")}
    if "payments_stripe_session_id_key" not in unique:
        op.create_unique_constraint("payments_stripe_session_id_key", "payments", ["stripe_session_id"])
    if not inspector.has_table("stripe_events"):
        op.create_table(
            "stripe_events",
            sa.Column("id", sa.String(255), primary_key=True),
            sa.Column("type", sa.String(80), nullable=False),
            sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    # Fees and Stripe references belong to real payments: refuse while any is recorded.
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT COUNT(*) FROM payments WHERE stripe_session_id IS NOT NULL")).scalar():
        raise RuntimeError("0011 cannot be downgraded: payments reference Stripe sessions.")
    if bind.execute(sa.text("SELECT COUNT(*) FROM doctor_profiles WHERE consultation_fee IS NOT NULL")).scalar():
        raise RuntimeError("0011 cannot be downgraded: doctors have set consultation fees.")
    inspector = sa.inspect(bind)
    if inspector.has_table("stripe_events"):
        op.drop_table("stripe_events")
    if "payments_stripe_session_id_key" in {u["name"] for u in inspector.get_unique_constraints("payments")}:
        op.drop_constraint("payments_stripe_session_id_key", "payments", type_="unique")
    for name in ("paid_at", "stripe_session_id", "currency"):
        op.drop_column("payments", name)
    op.drop_column("doctor_profiles", "consultation_fee")
