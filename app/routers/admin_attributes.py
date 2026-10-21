from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.deps import get_current_staff
from app.models import Attribute, AttributeOption, Category, Section
from app.schemas import AttributeIn, AttributeOut, OptionOut
from app.services import storage
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
async def save_attributes(items: list[AttributeIn], scope: str = Query(...), db: Session = Depends(get_db)):
    where, values = _scope(scope)
    if "category_id" in values and not db.get(Category, values["category_id"]):
        raise HTTPException(404, "Category not found")
    for path in replace_scope(db, where, values, items):
        await storage.delete(path)
    return list_attributes(scope, db)


@router.get("/categories/{cid}/attributes", response_model=list[AttributeOut])
def category_attributes(cid: int, db: Session = Depends(get_db)):
    """Everything a product of this category can be given: the division's attributes and the category's own."""
    c = db.get(Category, cid)
    if not c:
        raise HTTPException(404, "Category not found")
    return effective_attributes(db, c)


def _option(db: Session, oid: int) -> AttributeOption:
    o = db.get(AttributeOption, oid)
    if not o:
        raise HTTPException(404, "Option not found")
    return o


@router.post("/attribute-options/{oid}/image", response_model=OptionOut)
async def upload_option_image(oid: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """A small photo of a colour or decor, shown instead of the plain swatch."""
    o = _option(db, oid)
    path, url = await storage.upload(f"options/{oid}", await storage.read_and_optimise(file, max_side=480))
    old, o.image_path, o.image_url = o.image_path, path, url
    db.commit()
    if old:
        await storage.delete(old)
    return o


@router.delete("/attribute-options/{oid}/image", response_model=OptionOut)
async def remove_option_image(oid: int, db: Session = Depends(get_db)):
    o = _option(db, oid)
    old, o.image_path, o.image_url = o.image_path, None, None
    db.commit()
    if old:
        await storage.delete(old)
    return o
