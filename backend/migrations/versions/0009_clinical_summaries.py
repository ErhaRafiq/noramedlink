"""add clinical_summaries (versioned clinical summaries for doctors, ICSE)

Additive and guarded: a new table only; nothing existing is changed.

Revision ID: 0009
Revises: 0008
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "clinical_summaries"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(TABLE):
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("generated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("trigger", sa.String(300), nullable=False),
            sa.Column("input_fingerprint", sa.String(64), nullable=False),
            sa.Column("content_json", sa.JSON(), nullable=False),
            sa.Column("summary_text", sa.Text(), nullable=False),
            sa.Column("source", sa.String(40), nullable=False),
            sa.Column("is_current", sa.Boolean(), nullable=False),
            sa.UniqueConstraint("patient_id", "version", name="clinical_summaries_patient_id_version_key"),
        )
        inspector = sa.inspect(op.get_bind())
    existing = {index["name"] for index in inspector.get_indexes(TABLE)}
    if "ix_clinical_summaries_id" not in existing:
        op.create_index("ix_clinical_summaries_id", TABLE, ["id"])
    if "clinical_summaries_patient_id_generated_at_idx" not in existing:
        op.create_index("clinical_summaries_patient_id_generated_at_idx", TABLE, ["patient_id", "generated_at"])


def downgrade() -> None:
    # Summaries are derived, but a stored version is what a doctor saw: refuse to drop any.
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(TABLE):
        return
    if bind.execute(sa.text(f"SELECT COUNT(*) FROM {TABLE}")).scalar():
        raise RuntimeError("0009 cannot be downgraded: clinical_summaries has rows (versions doctors have seen).")
    op.drop_table(TABLE)
