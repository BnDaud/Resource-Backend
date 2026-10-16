"""Seed the initial categories and the site-settings row. Safe to run repeatedly."""
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Category
from app.services.common import get_site_settings, slugify

CATEGORIES = [
    "Boards & Plywood", "Flush Doors", "Door Boards", "Edges Tape", "Profiles", "Glass Profiles",
    "Kitchen Accessories", "Oven & Burners", "Heat Extractors", "Plate Racks", "Pull-Out Hanger Profiles",
    "Wine Racks", "Magic Corners", "Spoon Racks", "Microwave", "Other Products",
]

with SessionLocal() as db:
    have = set(db.scalars(select(Category.name)))
    for i, name in enumerate(CATEGORIES):
        if name not in have:
            db.add(Category(name=name, slug=slugify(name), sort_order=i))
    db.commit()
    get_site_settings(db)
    print("seeded", len(CATEGORIES), "categories + settings row")
