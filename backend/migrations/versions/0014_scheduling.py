"""add doctor availability, slot booking, reviews and appointment notifications (Module 5, Module 1 FE-3)

Additive and guarded: two new tables, new columns with defaults, and a partial unique index that keeps
one live appointment per doctor and start time. The index is skipped (and the app check still applies)
if existing data already holds a double booking; nothing is deleted or changed.

Revision ID: 0014
Revises: 0013
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SLOT_INDEX = "appointments_doctor_slot_uq"


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("doctor_availability"):
        op.create_table(
            "doctor_availability",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("weekday", sa.Integer(), nullable=False),
            sa.Column("start_time", sa.Time(), nullable=False),
            sa.Column("end_time", sa.Time(), nullable=False),
            sa.Column("slot_minutes", sa.Integer(), server_default="30", nullable=False),
        )
        op.create_index("doctor_availability_doctor_id_idx", "doctor_availability", ["doctor_id", "weekday"])

    if not inspector.has_table("appointment_reviews"):
        op.create_table(
            "appointment_reviews",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "appointment_id", sa.Integer(), sa.ForeignKey("appointments.id", ondelete="CASCADE"),
                nullable=False, unique=True,
            ),
            sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("rating", sa.Integer(), nullable=False),
            sa.Column("comment", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("appointment_reviews_doctor_id_idx", "appointment_reviews", ["doctor_id"])

    existing = _columns("appointments")
    if "duration_minutes" not in existing:
        op.add_column("appointments", sa.Column("duration_minutes", sa.Integer(), server_default="30", nullable=False))
    if "mode" not in existing:
        op.add_column("appointments", sa.Column("mode", sa.String(20), server_default="in_clinic", nullable=False))

    existing = _columns("notifications")
    if "appointment_id" not in existing:
        op.add_column(
            "notifications",
            sa.Column("appointment_id", sa.Integer(), sa.ForeignKey("appointments.id", ondelete="CASCADE"), nullable=True),
        )
    if "kind" not in existing:
        op.add_column("notifications", sa.Column("kind", sa.String(40), server_default="general", nullable=False))

    indexes = {i["name"] for i in sa.inspect(bind).get_indexes("appointments")}
    if SLOT_INDEX not in indexes:
        duplicates = bind.execute(
            sa.text(
                "SELECT COUNT(*) FROM (SELECT doctor_id, date FROM appointments WHERE status <> 'CANCELLED' "
                "AND doctor_id IS NOT NULL GROUP BY doctor_id, date HAVING COUNT(*) > 1) AS d"
            )
        ).scalar()
        if not duplicates:
            where = sa.text("status <> 'CANCELLED'")
            op.create_index(
                SLOT_INDEX, "appointments", ["doctor_id", "date"], unique=True,
                postgresql_where=where, sqlite_where=where,
            )


def downgrade() -> None:
    # Availability, reviews and notices are user data: refuse to drop them once they exist.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in ("doctor_availability", "appointment_reviews"):
        if inspector.has_table(table) and bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar():
            raise RuntimeError(f"0014 cannot be downgraded: {table} has rows.")
    if bind.execute(sa.text("SELECT COUNT(*) FROM notifications WHERE appointment_id IS NOT NULL")).scalar():
        raise RuntimeError("0014 cannot be downgraded: appointment notifications exist.")
    if SLOT_INDEX in {i["name"] for i in inspector.get_indexes("appointments")}:
        op.drop_index(SLOT_INDEX, table_name="appointments")
    for table in ("appointment_reviews", "doctor_availability"):
        if inspector.has_table(table):
            op.drop_table(table)
    op.drop_column("notifications", "kind")
    op.drop_column("notifications", "appointment_id")
    op.drop_column("appointments", "mode")
    op.drop_column("appointments", "duration_minutes")
