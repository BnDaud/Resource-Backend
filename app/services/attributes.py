"""Attributes (finish, colour, size, ...) and how they apply to categories and products."""
from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Attribute, AttributeOption, Category, Product, Section
from app.schemas import AttributeIn


def _order(a: Attribute) -> tuple:
    return (a.section is None, a.sort_order, a.id)  # division-wide attributes first


def effective_attributes(db: Session, category: Category) -> list[Attribute]:
    """What a category offers: its division's attributes plus its own."""
    rows = db.scalars(
        select(Attribute).where(or_(Attribute.category_id == category.id, Attribute.section == category.section))
        .options(selectinload(Attribute.options))
    ).all()
    return sorted(rows, key=_order)


def division_attributes(db: Session, section: Section) -> list[Attribute]:
    return sorted(db.scalars(select(Attribute).where(Attribute.section == section).options(selectinload(Attribute.options))).all(), key=_order)


def product_attributes(p: Product) -> list[dict]:
    """The product's options grouped under their attribute, in display order."""
    groups: dict[int, dict] = {}
    for o in p.options:
        a = o.attribute
        groups.setdefault(a.id, {"attr": a, "options": []})["options"].append(o)
    ordered = sorted(groups.values(), key=lambda g: _order(g["attr"]))
    return [{"id": g["attr"].id, "name": g["attr"].name, "customer_picks": g["attr"].customer_picks, "options": g["options"]} for g in ordered]


def check_product_options(db: Session, category_id: int, option_ids: list[int]) -> list[AttributeOption]:
    """The options must belong to the product's category (or its division)."""
    category = db.get(Category, category_id)
    allowed = {o.id: o for a in effective_attributes(db, category) for o in a.options}
    if any(i not in allowed for i in option_ids):
        raise HTTPException(422, "Some options do not belong to this category")
    return [allowed[i] for i in option_ids]


def replace_scope(db: Session, scope_filter, scope_values: dict, items: list[AttributeIn]) -> None:
    """Make the attributes of one scope (a division or a category) equal to `items`; ids that are left out are deleted,
    and deleting an option removes it from the products that had it."""
    existing = {a.id: a for a in db.scalars(select(Attribute).where(scope_filter).options(selectinload(Attribute.options)))}
    names = [i.name.lower() for i in items]
    if len(set(names)) != len(names):
        raise HTTPException(422, "Two attributes have the same name")
    keep: list[Attribute] = []
    for order, item in enumerate(items):
        if item.id is not None:
            attr = existing.get(item.id) or _bad_id("attribute")
        else:
            attr = Attribute(**scope_values)
            db.add(attr)
        attr.name, attr.filterable, attr.customer_picks, attr.sort_order = item.name, item.filterable, item.customer_picks, order
        keep.append(attr)
        have = {o.id: o for o in attr.options} if item.id is not None else {}
        kept_options = []
        for pos, o in enumerate(item.options):
            if o.id is not None:
                opt = have.get(o.id) or _bad_id("option")
            else:
                opt = AttributeOption()
                attr.options.append(opt)
            opt.label, opt.color, opt.sort_order = o.label, o.color, pos
            kept_options.append(opt)
        for o in list(attr.options):
            if o not in kept_options:
                attr.options.remove(o)
    for attr in existing.values():
        if attr not in keep:
            db.delete(attr)
    db.commit()


def _bad_id(what: str):
    raise HTTPException(422, f"Unknown {what}: reload the page and try again")
