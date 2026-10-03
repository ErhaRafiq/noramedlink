"""add appointments.specialty and appointments.reason (declared by the Prisma schema)

Additive and guarded.

Revision ID: 0006
Revises: 0005
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("appointments")}
    for name in ("specialty", "reason"):
        if name not in existing:
            op.add_column("appointments", sa.Column(name, sa.Text(), nullable=True))


def downgrade() -> None:
    # Dropping these columns would lose booking details; refuse instead.
    raise NotImplementedError("0006 cannot be downgraded without data loss.")
