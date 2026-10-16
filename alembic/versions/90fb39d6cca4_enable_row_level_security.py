"""enable row level security

Revision ID: 90fb39d6cca4
Revises: b686a275bd79
Create Date: 2026-10-12 20:12:57.411496

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '90fb39d6cca4'
down_revision: Union[str, None] = 'b686a275bd79'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES = [
    "staff", "categories", "products", "product_images", "product_specs", "quote_requests",
    "quote_items", "enquiries", "testimonials", "site_settings", "alembic_version",
]


def upgrade() -> None:
    # Supabase exposes the public schema over its REST API with the public anon key.
    # RLS with no policies blocks that route completely; the backend connects as the
    # database owner, which bypasses RLS, so it is unaffected.
    for t in TABLES:
        op.execute(f'ALTER TABLE public."{t}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    for t in TABLES:
        op.execute(f'ALTER TABLE public."{t}" DISABLE ROW LEVEL SECURITY')
