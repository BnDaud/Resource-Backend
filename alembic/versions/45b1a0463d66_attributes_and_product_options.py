"""attributes and product options

Adds attributes (finish, colour, size, ... per division or category), their options, and the options each product has.
Existing product sizes and colours are copied across as a "Size" and a "Colour" attribute of the product's category.
The old columns are made optional here and dropped in the next migration, after the new backend is deployed.

Revision ID: 45b1a0463d66
Revises: ec448be92e0c
"""
from alembic import op
import sqlalchemy as sa

revision = "45b1a0463d66"
down_revision = "ec448be92e0c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attributes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("categories.id", ondelete="CASCADE"), nullable=True),
        sa.Column("section", sa.String(20), nullable=True),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("filterable", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("customer_picks", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.CheckConstraint("(category_id IS NULL) <> (section IS NULL)", name="ck_attribute_one_scope"),
    )
    op.create_index("ix_attributes_category_id", "attributes", ["category_id"])
    op.create_index("ix_attributes_section", "attributes", ["section"])
    op.create_table(
        "attribute_options",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("attribute_id", sa.Integer, sa.ForeignKey("attributes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(60), nullable=False),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_attribute_options_attribute_id", "attribute_options", ["attribute_id"])
    op.create_table(
        "product_options",
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("option_id", sa.Integer, sa.ForeignKey("attribute_options.id", ondelete="CASCADE"), primary_key=True),
    )
    op.alter_column("products", "sizes", existing_type=sa.JSON, nullable=True)
    op.alter_column("products", "colours", existing_type=sa.JSON, nullable=True)
    _copy_sizes_and_colours()


def _copy_sizes_and_colours() -> None:
    conn = op.get_bind()
    products = sa.table("products", sa.column("id", sa.Integer), sa.column("category_id", sa.Integer), sa.column("sizes", sa.JSON), sa.column("colours", sa.JSON))
    attributes = sa.table("attributes", sa.column("id", sa.Integer), sa.column("category_id", sa.Integer), sa.column("name", sa.String), sa.column("sort_order", sa.Integer))
    options = sa.table("attribute_options", sa.column("id", sa.Integer), sa.column("attribute_id", sa.Integer), sa.column("label", sa.String), sa.column("sort_order", sa.Integer))
    links = sa.table("product_options", sa.column("product_id", sa.Integer), sa.column("option_id", sa.Integer))
    rows = conn.execute(sa.select(products.c.id, products.c.category_id, products.c.sizes, products.c.colours)).all()
    for order, (name, index) in enumerate((("Size", 2), ("Colour", 3))):
        labels: dict[int, list[str]] = {}          # category -> labels in the order they first appear
        for r in rows:
            for label in (r[index] or []):
                if label not in labels.setdefault(r.category_id, []):
                    labels[r.category_id].append(label)
        for category_id, names in labels.items():
            attribute_id = conn.execute(sa.insert(attributes).values(category_id=category_id, name=name, sort_order=order).returning(attributes.c.id)).scalar_one()
            ids = {}
            for pos, label in enumerate(names):
                ids[label] = conn.execute(sa.insert(options).values(attribute_id=attribute_id, label=label, sort_order=pos).returning(options.c.id)).scalar_one()
            for r in rows:
                if r.category_id == category_id:
                    for label in dict.fromkeys(r[index] or []):
                        conn.execute(sa.insert(links).values(product_id=r.id, option_id=ids[label]))


def downgrade() -> None:
    op.drop_table("product_options")
    op.drop_table("attribute_options")
    op.drop_table("attributes")
    op.alter_column("products", "sizes", existing_type=sa.JSON, nullable=False)
    op.alter_column("products", "colours", existing_type=sa.JSON, nullable=False)
