"""add public uuid ids

Revision ID: 1546b4a7001c
Revises: a20f4211496a
Create Date: 2026-10-12 21:55:47.640874

"""
from typing import Sequence, Union

import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1546b4a7001c'
down_revision: Union[str, None] = 'a20f4211496a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES = ["products", "quote_requests", "enquiries"]


def upgrade() -> None:
    # Public ids are random UUIDs, so URLs do not reveal how many products or requests exist.
    # Existing rows get a UUID backfilled before the column becomes NOT NULL + UNIQUE.
    conn = op.get_bind()
    for t in TABLES:
        op.add_column(t, sa.Column("uid", sa.String(36), nullable=True))
        for (rid,) in conn.execute(sa.text(f"SELECT id FROM {t}")).all():
            conn.execute(sa.text(f"UPDATE {t} SET uid = :u WHERE id = :i"), {"u": str(uuid.uuid4()), "i": rid})
        op.alter_column(t, "uid", nullable=False)
        op.create_index(f"ix_{t}_uid", t, ["uid"], unique=True)


def downgrade() -> None:
    for t in TABLES:
        op.drop_index(f"ix_{t}_uid", table_name=t)
        op.drop_column(t, "uid")
