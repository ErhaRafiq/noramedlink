"""add medication schedule columns: instructions, start_date, end_date

Additive and guarded. The Prisma model's patient_id and medicine_name columns are
intentionally not added: they duplicate user_id and name, which the API maps instead.

Revision ID: 0004
Revises: 0003
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = [
    ("instructions", sa.Text()),
    ("start_date", sa.Date()),
    ("end_date", sa.Date()),
]


def upgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("medications")}
    for name, type_ in COLUMNS:
        if name not in existing:
            op.add_column("medications", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    # Dropping these columns would lose schedule data; refuse instead.
    raise NotImplementedError("0004 cannot be downgraded without data loss.")
