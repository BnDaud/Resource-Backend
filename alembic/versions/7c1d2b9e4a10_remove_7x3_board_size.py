"""remove the 7x3 ft board size

The client only stocks 8x4 ft boards. Deletes the "7x3 ft" Size option and its links to products.

Revision ID: 7c1d2b9e4a10
Revises: 2ed91808de3c
"""
from alembic import op

revision = "7c1d2b9e4a10"
down_revision = "2ed91808de3c"
branch_labels = None
depends_on = None

_IDS = "SELECT o.id FROM attribute_options o JOIN attributes a ON a.id = o.attribute_id WHERE a.name = 'Size' AND o.label = '7x3 ft'"


def upgrade() -> None:
    op.execute(f"DELETE FROM product_options WHERE option_id IN ({_IDS})")
    op.execute(f"DELETE FROM attribute_options WHERE id IN ({_IDS})")


def downgrade() -> None:
    pass  # the removed option is not restored; add it again from the CMS if ever needed
