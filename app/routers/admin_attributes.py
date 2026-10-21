from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.deps import get_current_staff
from app.models import Attribute, Category, Section
from app.schemas import AttributeIn, AttributeOut
from app.services.attributes import effective_attributes, replace_scope

router = APIRouter(prefix="/api/v1/admin", tags=["admin-attributes"], dependencies=[Depends(get_current_staff)])


def _scope(scope: str):
    """'section:boards' or 'category:12' -> (SQL filter, values for a new attribute)."""
    kind, _, value = scope.partition(":")
    if kind == "section" and value in {s.value for s in Section}:
        return Attribute.section == Section(value), {"section": Section(value)}
    if kind == "category" and value.isdigit():
        return Attribute.category_id == int(value), {"category_id": int(value)}
    raise HTTPException(422, "Scope must look like section:boards or category:12")


@router.get("/attributes", response_model=list[AttributeOut])
def list_attributes(scope: str = Query(...), db: Session = Depends(get_db)):
    """The attributes defined for one division or one category (not the inherited ones)."""
    where, _ = _scope(scope)
    rows = db.scalars(select(Attribute).where(where).options(selectinload(Attribute.options)).order_by(Attribute.sort_order, Attribute.id)).all()
    return rows


@router.put("/attributes", response_model=list[AttributeOut])
def save_attributes(items: list[AttributeIn], scope: str = Query(...), db: Session = Depends(get_db)):
    where, values = _scope(scope)
    if "category_id" in values and not db.get(Category, values["category_id"]):
        raise HTTPException(404, "Category not found")
    replace_scope(db, where, values, items)
    return list_attributes(scope, db)


@router.get("/categories/{cid}/attributes", response_model=list[AttributeOut])
def category_attributes(cid: int, db: Session = Depends(get_db)):
    """Everything a product of this category can be given: the division's attributes and the category's own."""
    c = db.get(Category, cid)
    if not c:
        raise HTTPException(404, "Category not found")
    return effective_attributes(db, c)
