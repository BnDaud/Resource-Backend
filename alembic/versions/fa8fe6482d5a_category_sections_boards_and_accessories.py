"""category sections: boards and accessories

Adds categories.section and moves the catalogue to the two divisions the shop sells:
  boards:      HDF, MDF, Blockboard
  accessories: everything else (Oven & Burners is split into Burners and Oven; Door Boards and Flush Doors are retired)

Revision ID: fa8fe6482d5a
Revises: e4ff4a21c559
"""
from alembic import op
import sqlalchemy as sa

revision = "fa8fe6482d5a"
down_revision = "e4ff4a21c559"
branch_labels = None
depends_on = None

ORDER = [  # name, section: the new category order
    ("HDF", "boards"), ("MDF", "boards"), ("Blockboard", "boards"),
    ("Microwave", "accessories"), ("Heat Extractors", "accessories"), ("Burners", "accessories"), ("Oven", "accessories"),
    ("Kitchen Accessories", "accessories"), ("Plate Racks", "accessories"), ("Wine Racks", "accessories"),
    ("Spoon Racks", "accessories"), ("Pull-Out Hanger Profiles", "accessories"), ("Magic Corners", "accessories"),
    ("Edges Tape", "accessories"), ("Profiles", "accessories"), ("Glass Profiles", "accessories"), ("Other Products", "accessories"),
]
RETIRED = ("flush-doors", "door-boards")
RENAMED = {"boards-plywood": ("HDF", "hdf"), "oven-burners": ("Burners", "burners")}

categories = sa.table(
    "categories", sa.column("id", sa.Integer), sa.column("name", sa.String), sa.column("slug", sa.String), sa.column("section", sa.String),
    sa.column("sort_order", sa.Integer), sa.column("description", sa.Text), sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
products = sa.table("products", sa.column("category_id", sa.Integer))


def slugify(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-").replace("--", "-")


def upgrade() -> None:
    op.add_column("categories", sa.Column("section", sa.String(20), nullable=False, server_default="accessories"))
    op.create_index("ix_categories_section", "categories", ["section"])
    conn = op.get_bind()

    for slug in RETIRED:  # only removable when empty: never delete a customer's products silently
        row = conn.execute(sa.select(categories.c.id).where(categories.c.slug == slug)).first()
        if row is None:
            continue
        if conn.execute(sa.select(sa.func.count()).select_from(products).where(products.c.category_id == row.id)).scalar():
            raise RuntimeError(f"Category '{slug}' still has products. Move or delete them, then run the migration again.")
        conn.execute(sa.delete(categories).where(categories.c.id == row.id))

    for old_slug, (name, slug) in RENAMED.items():
        conn.execute(sa.update(categories).where(categories.c.slug == old_slug).values(name=name, slug=slug))

    have = {r.slug for r in conn.execute(sa.select(categories.c.slug))}
    for i, (name, section) in enumerate(ORDER):
        slug = slugify(name)
        if slug not in have:
            conn.execute(sa.insert(categories).values(name=name, slug=slug, section=section, sort_order=i, description="",
                                                      created_at=sa.func.now(), updated_at=sa.func.now()))
        else:
            conn.execute(sa.update(categories).where(categories.c.slug == slug).values(section=section, sort_order=i))


def downgrade() -> None:
    # The renamed and retired categories are not restored: only the new column is removed.
    op.drop_index("ix_categories_section", table_name="categories")
    op.drop_column("categories", "section")
