"""enquiry reference

Revision ID: e4ff4a21c559
Revises: 1546b4a7001c
Create Date: 2026-10-13 20:04:21.736861

"""
from typing import Sequence, Union

import secrets

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4ff4a21c559'
down_revision: Union[str, None] = '1546b4a7001c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    op.add_column("enquiries", sa.Column("reference", sa.String(20), nullable=True))
    used: set[str] = set()
    for rid, created in conn.execute(sa.text("SELECT id, created_at FROM enquiries")).all():
        while True:
            ref = f"EN-{created:%y%m%d}-" + "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(4))
            if ref not in used:
                break
        used.add(ref)
        conn.execute(sa.text("UPDATE enquiries SET reference = :r WHERE id = :i"), {"r": ref, "i": rid})
    op.alter_column("enquiries", "reference", nullable=False)
    op.create_index("ix_enquiries_reference", "enquiries", ["reference"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_enquiries_reference", table_name="enquiries")
    op.drop_column("enquiries", "reference")
