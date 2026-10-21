"""drop product sizes and colours

Sizes and colours are now attributes with options. Run this only after the backend that no longer reads the two columns is deployed.

Revision ID: 857401274900
Revises: 45b1a0463d66
"""
from alembic import op
import sqlalchemy as sa

revision = "857401274900"
down_revision = "45b1a0463d66"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("products", "sizes")
    op.drop_column("products", "colours")


def downgrade() -> None:
    op.add_column("products", sa.Column("sizes", sa.JSON, nullable=True))
    op.add_column("products", sa.Column("colours", sa.JSON, nullable=True))
