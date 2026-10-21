"""Seed the initial categories (two divisions), their filters and options, and the site-settings row. Safe to run repeatedly:
it adds what is missing and never changes or removes what staff have edited."""
import json
from pathlib import Path

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models import Attribute, AttributeOption, Category, Section
from app.services.common import get_site_settings, slugify

B, A = Section.boards, Section.accessories
CATEGORIES = [
    ("HDF", B), ("MDF", B), ("Blockboard", B),
    ("Microwave", A), ("Heat Extractors", A), ("Burners", A), ("Oven", A), ("Kitchen Accessories", A), ("Plate Racks", A),
    ("Wine Racks", A), ("Spoon Racks", A), ("Pull-Out Hanger Profiles", A), ("Magic Corners", A), ("Edges Tape", A),
    ("Profiles", A), ("Glass Profiles", A), ("Other Products", A),
]

COLOURS = [("Red", "#c0392b"), ("White", "#ffffff"), ("Green", "#2e7d32"), ("Off-white", "#f3efe4"), ("Cream", "#f2e6c4"), ("Black", "#1c1c1c"), ("Grey", "#8d9196")]
DEVICE_COLOURS = [("Black", "#1c1c1c"), ("White", "#ffffff"), ("Silver", "#c0c3c7"), ("Stainless steel", "#a9adb2")]
PIECE_COLOURS = [("Black", "#1c1c1c"), ("White", "#ffffff"), ("Grey", "#8d9196"), ("Chrome", "#c0c3c7")]


# The standard RAL Classic colour range (code, name, on-screen colour). The printed colour sheet is the reference.
RAL = [(c["name"], c["hex"], c["code"]) for c in json.loads((Path(__file__).parent / "ral_classic.json").read_text(encoding="utf-8"))]


def attr(name, options, *, filterable=True, picks=True):
    return (name, filterable, picks, options)


# What a division or a category offers. A division's attributes apply to all of its categories.
SCOPES = {
    ("section", "boards"): [
        attr("Finish", ["Matte", "Glossy"]),
        attr("Colour type", ["Simple colours", "Complex colours"], picks=False),
        attr("Colour", COLOURS),
        attr("Special colour", RAL),
        attr("Pattern", ["Synthetic", "Synchronized"]),
        attr("Size", ["8x4 ft", "7x3 ft"]),
        attr("Thickness", ["6 mm", "9 mm", "12 mm", "16 mm", "18 mm"]),
    ],
    ("category", "Microwave"): [
        attr("Capacity", ["20 L", "25 L", "30 L"]), attr("Grill", ["Yes", "No"], picks=False),
        attr("Install", ["Built-in", "Countertop"], picks=False), attr("Colour", DEVICE_COLOURS),
    ],
    ("category", "Heat Extractors"): [
        attr("Control", ["Automatic (hand-wave sensor)", "Manual"], picks=False), attr("Size", ["60 cm", "90 cm"]),
        attr("Type", ["Wall-mounted", "Built-in"], picks=False), attr("Colour", DEVICE_COLOURS),
    ],
    ("category", "Burners"): [
        attr("Burners", ["2", "3", "4", "5"], picks=False), attr("Width", ["60 cm", "75 cm", "90 cm"]),
        attr("Ignition", ["Automatic", "Manual"], picks=False), attr("Surface", ["Glass", "Stainless steel"], picks=False),
        attr("Colour", DEVICE_COLOURS),
    ],
    ("category", "Oven"): [
        attr("Size", ["60 cm", "90 cm"]), attr("Functions", ["Grill", "Fan"], picks=False),
        attr("Install", ["Built-in", "Freestanding"], picks=False), attr("Colour", DEVICE_COLOURS),
    ],
    ("category", "Kitchen Accessories"): [attr("Size", ["Small", "Standard", "Large"]), attr("Material", ["Steel", "Plastic", "Zinc alloy"], picks=False), attr("Colour", PIECE_COLOURS)],
    ("category", "Plate Racks"): [attr("Size", ["Compact", "Standard"]), attr("Material", ["Chrome", "Stainless steel", "Plastic"], picks=False), attr("Colour", PIECE_COLOURS)],
    ("category", "Wine Racks"): [attr("Capacity", ["12 bottles", "18 bottles", "24 bottles", "36 bottles"]), attr("Mount", ["Wall", "Floor"], picks=False), attr("Material", ["Metal", "Wood"], picks=False), attr("Colour", PIECE_COLOURS)],
    ("category", "Spoon Racks"): [attr("Size", ["Small", "Large", "60 cm", "90 cm"]), attr("Material", ["Stainless steel", "Ceramic", "Wood"], picks=False), attr("Colour", PIECE_COLOURS)],
    ("category", "Pull-Out Hanger Profiles"): [attr("Size", ["450 mm", "550 mm", "650 mm"]), attr("Mount", ["Side", "Telescopic"], picks=False), attr("Colour", PIECE_COLOURS)],
    ("category", "Magic Corners"): [attr("Cabinet width", ["450 mm", "500 mm", "600 mm"]), attr("Opening", ["Left", "Right"]), attr("Colour", PIECE_COLOURS)],
    ("category", "Edges Tape"): [
        attr("Width", ["22 mm", "45 mm"]), attr("Thickness", ["0.4 mm", "1 mm", "2 mm"]), attr("Material", ["PVC", "Wood veneer"], picks=False),
        attr("Colour", [("White", "#ffffff"), ("Oak", "#b88a54"), ("Walnut", "#5c4033"), ("Maple", "#d9b382"), "Clear", "Yellow"]),
    ],
    ("category", "Profiles"): [attr("Type", ["Angle", "Channel", "Tube", "Heat-sink"], picks=False), attr("Length", ["1 m", "2 m", "3 m"]), attr("Finish", ["Silver", "Black", "Brushed anodised"])],
    ("category", "Glass Profiles"): [attr("Type", ["Frame", "Partition"], picks=False), attr("Length", ["3 m"]), attr("Finish", ["Matt black", "Silver"])],
    ("category", "Other Products"): [attr("Size", ["Standard"]), attr("Finish", ["Brass", "Satin steel", "Black"])],
}


def seed_attributes(db, categories: dict[str, Category]) -> None:
    for (kind, key), definitions in SCOPES.items():
        where, values = (Attribute.section == Section(key), {"section": Section(key)}) if kind == "section" else (
            Attribute.category_id == categories[key].id, {"category_id": categories[key].id})
        have = {a.name.lower(): a for a in db.scalars(select(Attribute).where(where))}
        for order, (name, filterable, picks, options) in enumerate(definitions):
            a = have.get(name.lower())
            if a is None:
                a = Attribute(name=name, filterable=filterable, customer_picks=picks, sort_order=order, **values)
                db.add(a)
                db.flush()
            have_options = {(o.code or o.label).lower() for o in a.options}
            for label, color, code in ((o, None, None) if isinstance(o, str) else (o + (None,))[:3] for o in options):
                if (code or label).lower() not in have_options:
                    a.options.append(AttributeOption(label=label, color=color, code=code, sort_order=len(a.options)))
    db.commit()


with SessionLocal() as db:
    have = set(db.scalars(select(Category.name)))
    for i, (name, section) in enumerate(CATEGORIES):
        if name not in have:
            db.add(Category(name=name, slug=slugify(name), sort_order=i, section=section))
    db.commit()
    seed_attributes(db, {c.name: c for c in db.scalars(select(Category))})
    get_site_settings(db)
    print("seeded", len(CATEGORIES), "categories,", db.scalar(select(func.count()).select_from(Attribute)), "attributes + settings row")
