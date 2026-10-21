from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.deps import get_current_staff
from app.models import Category, Product
from app.schemas import CategoryIn, CategoryOut
from app.services.common import unique_slug

router = APIRouter(prefix="/api/v1/admin", tags=["admin-categories"], dependencies=[Depends(get_current_staff)])


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.scalars(select(Category).order_by(Category.sort_order, Category.name)).all()


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryIn, db: Session = Depends(get_db)):
    if db.scalar(select(Category.id).where(func.lower(Category.name) == data.name.strip().lower())):
        raise HTTPException(409, "A category with this name already exists")
    c = Category(name=data.name.strip(), description=data.description, sort_order=data.sort_order, section=data.section)
    c.slug = unique_slug(db, Category, c.name)
    db.add(c)
    db.commit()
    return c


@router.put("/categories/{cid}", response_model=CategoryOut)
def update_category(cid: int, data: CategoryIn, db: Session = Depends(get_db)):
    c = db.get(Category, cid) or _not_found()
    dup = db.scalar(select(Category.id).where(func.lower(Category.name) == data.name.strip().lower(), Category.id != cid))
    if dup:
        raise HTTPException(409, "A category with this name already exists")
    c.name, c.description, c.sort_order, c.section = data.name.strip(), data.description, data.sort_order, data.section
    c.slug = unique_slug(db, Category, c.name, exclude_id=cid)
    db.commit()
    return c


@router.delete("/categories/{cid}", status_code=204)
def delete_category(cid: int, db: Session = Depends(get_db)):
    c = db.get(Category, cid) or _not_found()
    if db.scalar(select(func.count()).select_from(Product).where(Product.category_id == cid)):
        raise HTTPException(409, "Move or archive this category's products first")
    db.delete(c)
    db.commit()






def _not_found():
    raise HTTPException(404, "Category not found")
