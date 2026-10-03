"""add medicine_reminders and reminder_logs (Prisma models MedicineReminder, ReminderLog)

Additive and guarded: each table is created only if it does not exist yet.

Revision ID: 0005
Revises: 0004
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    if "medicine_reminders" not in existing:
        op.create_table(
            "medicine_reminders",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("medication_id", sa.Integer(), sa.ForeignKey("medications.id", ondelete="CASCADE"), nullable=False),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("reminder_time", sa.DateTime(timezone=True), nullable=False),
            sa.Column("frequency", sa.Text(), nullable=False),
            sa.Column("status", sa.Text(), server_default="UPCOMING", nullable=False),
            sa.Column("taken_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("skipped_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("medicine_reminders_patient_id_reminder_time_idx", "medicine_reminders", ["patient_id", "reminder_time"])
        op.create_index("medicine_reminders_medication_id_idx", "medicine_reminders", ["medication_id"])

    if "reminder_logs" not in existing:
        op.create_table(
            "reminder_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("reminder_id", sa.Integer(), sa.ForeignKey("medicine_reminders.id", ondelete="CASCADE"), nullable=False),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", sa.Text(), nullable=False),
            sa.Column("taken_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("reminder_logs_patient_id_scheduled_for_idx", "reminder_logs", ["patient_id", "scheduled_for"])
        op.create_index("reminder_logs_reminder_id_idx", "reminder_logs", ["reminder_id"])


def downgrade() -> None:
    # Dropping these tables would delete reminder history; refuse instead.
    raise NotImplementedError("0005 cannot be downgraded without data loss.")
