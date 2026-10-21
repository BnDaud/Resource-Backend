"""option code and photo

Options (finish, colour, size, ...) can carry a catalogue code such as RAL 3020 and an optional photo, so a long colour sheet
can be shown as a visual grid.

Revision ID: 2ed91808de3c
Revises: 857401274900
"""
from alembic import op
import sqlalchemy as sa

revision = "2ed91808de3c"
down_revision = "857401274900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attribute_options", sa.Column("code", sa.String(40), nullable=True))
    op.add_column("attribute_options", sa.Column("image_url", sa.String(500), nullable=True))
    op.add_column("attribute_options", sa.Column("image_path", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("attribute_options", "image_path")
    op.drop_column("attribute_options", "image_url")
    op.drop_column("attribute_options", "code")
