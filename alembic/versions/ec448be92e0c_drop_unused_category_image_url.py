"""drop unused category image_url

Category photos come from the products (the first main image of a representative product), so this column was never set.
Run it only after the backend that no longer reads the column is deployed.

Revision ID: ec448be92e0c
Revises: fa8fe6482d5a
"""
from alembic import op
import sqlalchemy as sa

revision = "ec448be92e0c"
down_revision = "fa8fe6482d5a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("categories", "image_url")


def downgrade() -> None:
    op.add_column("categories", sa.Column("image_url", sa.String(500), nullable=True))
