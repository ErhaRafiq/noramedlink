"""add patient contact/emergency details and doctor profile details (Module 1, FE-2 and FE-3)

Additive and guarded: nullable columns only (one with a default); nothing existing is changed.

Revision ID: 0013
Revises: 0012
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PATIENT_COLUMNS = [
    sa.Column("city", sa.String(80), nullable=True),
    sa.Column("address", sa.String(240), nullable=True),
    sa.Column("blood_group", sa.String(3), nullable=True),
    sa.Column("emergency_contact_name", sa.String(120), nullable=True),
    sa.Column("emergency_contact_phone", sa.String(40), nullable=True),
]
DOCTOR_COLUMNS = [
    sa.Column("qualifications", sa.Text(), nullable=True),
    sa.Column("experience_years", sa.Integer(), nullable=True),
    sa.Column("bio", sa.Text(), nullable=True),
    sa.Column("city", sa.String(80), nullable=True),
    sa.Column("languages", sa.String(200), nullable=True),
    sa.Column("consultation_modes", sa.String(40), server_default="in_clinic", nullable=False),
]


def _add_missing(table: str, columns: list[sa.Column]) -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
    for column in columns:
        if column.name not in existing:
            op.add_column(table, column)


def upgrade() -> None:
    _add_missing("patient_profiles", PATIENT_COLUMNS)
    _add_missing("doctor_profiles", DOCTOR_COLUMNS)


def downgrade() -> None:
    # Profile details are the user's own data: refuse to drop them once any is filled in.
    bind = op.get_bind()
    for table, columns in (("patient_profiles", PATIENT_COLUMNS), ("doctor_profiles", DOCTOR_COLUMNS)):
        existing = {c["name"] for c in sa.inspect(bind).get_columns(table)}
        for column in columns:
            if column.name in existing and column.name != "consultation_modes":
                if bind.execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE {column.name} IS NOT NULL")).scalar():
                    raise RuntimeError(f"0013 cannot be downgraded: {table}.{column.name} holds user data.")
    for table, columns in (("doctor_profiles", DOCTOR_COLUMNS), ("patient_profiles", PATIENT_COLUMNS)):
        existing = {c["name"] for c in sa.inspect(bind).get_columns(table)}
        for column in columns:
            if column.name in existing:
                op.drop_column(table, column.name)
