"""Seed the initial categories (two divisions: boards and accessories) and the site-settings row. Safe to run repeatedly."""
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Category, Section
from app.services.common import get_site_settings, slugify

B, A = Section.boards, Section.accessories
CATEGORIES = [
    ("HDF", B), ("MDF", B), ("Blockboard", B),
    ("Microwave", A), ("Heat Extractors", A), ("Burners", A), ("Oven", A), ("Kitchen Accessories", A), ("Plate Racks", A),
    ("Wine Racks", A), ("Spoon Racks", A), ("Pull-Out Hanger Profiles", A), ("Magic Corners", A), ("Edges Tape", A),
    ("Profiles", A), ("Glass Profiles", A), ("Other Products", A),
]

with SessionLocal() as db:
    have = set(db.scalars(select(Category.name)))
    for i, (name, section) in enumerate(CATEGORIES):
        if name not in have:
            db.add(Category(name=name, slug=slugify(name), sort_order=i, section=section))
    db.commit()
    get_site_settings(db)
    print("seeded", len(CATEGORIES), "categories + settings row")
