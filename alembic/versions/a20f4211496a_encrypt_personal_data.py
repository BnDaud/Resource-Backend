"""encrypt personal data

Revision ID: a20f4211496a
Revises: 90fb39d6cca4
Create Date: 2026-10-12 20:21:11.924642

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a20f4211496a'
down_revision: Union[str, None] = '90fb39d6cca4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ENC = {
    "staff": ["email", "name"],
    "quote_requests": ["full_name", "phone", "email", "company", "message", "internal_notes"],
    "enquiries": ["name", "email", "phone", "subject", "message", "internal_notes"],
    "products": ["wholesale_note"],
}


def upgrade() -> None:
    conn = op.get_bind()
    # Existing rows would be plaintext. Refuse rather than silently mix plaintext and ciphertext.
    for t in ("staff", "quote_requests", "enquiries"):
        if conn.execute(sa.text(f"SELECT count(*) FROM {t}")).scalar():
            raise RuntimeError(f"{t} already has rows; run scripts/encrypt_existing.py instead of this migration")
    if conn.execute(sa.text("SELECT count(*) FROM products WHERE wholesale_note <> '' OR stock_qty IS NOT NULL")).scalar():
        raise RuntimeError("products have private data; encrypt them before migrating")

    op.drop_index("ix_staff_email", table_name="staff")
    op.drop_index("ix_quote_requests_phone", table_name="quote_requests")
    for table, cols in ENC.items():
        for c in cols:
            op.alter_column(table, c, type_=sa.Text(), existing_nullable=False)
    op.execute("ALTER TABLE products ALTER COLUMN stock_qty TYPE TEXT USING NULL")
    op.add_column("staff", sa.Column("email_hash", sa.String(32), nullable=False, server_default=""))
    op.alter_column("staff", "email_hash", server_default=None)
    op.create_index("ix_staff_email_hash", "staff", ["email_hash"], unique=True)
    op.add_column("quote_requests", sa.Column("search_tokens", sa.Text(), nullable=False, server_default=""))
    op.add_column("enquiries", sa.Column("search_tokens", sa.Text(), nullable=False, server_default=""))



def downgrade() -> None:
    raise RuntimeError("Irreversible: decrypting data back to plaintext columns is intentionally unsupported")
