import math
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.db import get_db
from app.deps import get_current_staff
from app.models import Availability, Category, Product, ProductImage, ProductSpec
from app.routers.public import to_detail
from app.schemas import ImageOut, Page, ProductAdmin, ProductIn
from app.services import storage
from app.services.common import escape_like, unique_slug

router = APIRouter(prefix="/api/v1/admin", tags=["admin-catalog"], dependencies=[Depends(get_current_staff)])


def _nf(what: str):
    raise HTTPException(404, f"{what} not found")


# ---------------- products ----------------
def _load(db: Session, pid: UUID) -> Product:
    p = db.scalar(
        select(Product).where(Product.uid == str(pid))
        .options(selectinload(Product.images), selectinload(Product.specs), joinedload(Product.category))
        .execution_options(populate_existing=True)
    )
    return p or _nf("Product")


def _out(p: Product) -> dict:
    return {**to_detail(p), "wholesale_note": p.wholesale_note, "stock_qty": p.stock_qty,
            "is_archived": p.is_archived, "updated_at": p.updated_at,
            "public_price": p.public_price if p.price_mode.value == "public" else None}


@router.get("/products", response_model=Page[ProductAdmin])
def list_products(
    db: Session = Depends(get_db),
    q: str | None = Query(None, max_length=100),
    category_id: int | None = None,
    availability: Availability | None = None,
    archived: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    stmt = select(Product).where(Product.is_archived.is_(archived))
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if availability:
        stmt = stmt.where(Product.availability == availability)
    if q and q.strip():
        like = f"%{escape_like(q.strip())}%"
        stmt = stmt.where(or_(Product.name.ilike(like, escape="\\"), Product.sku.ilike(like, escape="\\")))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.options(selectinload(Product.images), selectinload(Product.specs), joinedload(Product.category))
        .order_by(Product.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return Page(items=[_out(p) for p in rows], total=total, page=page, page_size=page_size,
                pages=max(1, math.ceil(total / page_size)))


@router.get("/products/{pid}", response_model=ProductAdmin)
def get_product(pid: UUID, db: Session = Depends(get_db)):
    return _out(_load(db, pid))


def _apply(p: Product, data: ProductIn):
    for f in ("name", "sku", "category_id", "brand", "short_description", "description", "sizes", "colours",
              "availability", "price_mode", "public_price", "wholesale_note", "stock_qty", "is_featured", "is_new"):
        setattr(p, f, getattr(data, f))
    p.specs = [ProductSpec(name=s.name, value=s.value, sort_order=i) for i, s in enumerate(data.specs)]


def _commit(db: Session):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That SKU is already used by another product")


@router.post("/products", response_model=ProductAdmin, status_code=201)
def create_product(data: ProductIn, db: Session = Depends(get_db)):
    if not db.get(Category, data.category_id):
        raise HTTPException(422, "Choose a valid category")
    p = Product()
    _apply(p, data)
    p.slug = unique_slug(db, Product, data.name)
    db.add(p)
    _commit(db)
    return _out(_load(db, UUID(p.uid)))


@router.put("/products/{pid}", response_model=ProductAdmin)
def update_product(pid: UUID, data: ProductIn, db: Session = Depends(get_db)):
    p = _load(db, pid)
    if not db.get(Category, data.category_id):
        raise HTTPException(422, "Choose a valid category")
    renamed = data.name != p.name
    _apply(p, data)
    if renamed:
        p.slug = unique_slug(db, Product, data.name, exclude_id=p.id)
    _commit(db)
    return _out(_load(db, pid))


@router.patch("/products/{pid}/archive", response_model=ProductAdmin)
def set_archived(pid: UUID, archived: bool = True, db: Session = Depends(get_db)):
    """Archive instead of delete: hides the product but keeps quote history and links intact."""
    p = _load(db, pid)
    p.is_archived = archived
    db.commit()
    return _out(_load(db, pid))


@router.post("/products/{pid}/images", response_model=ImageOut, status_code=201)
async def upload_image(pid: UUID, file: UploadFile = File(...), db: Session = Depends(get_db)):
    p = _load(db, pid)
    count = db.scalar(select(func.count()).select_from(ProductImage).where(ProductImage.product_id == p.id)) or 0
    if count >= 12:
        raise HTTPException(422, "A product can have at most 12 images")
    data = await storage.read_and_optimise(file)
    path, url = await storage.upload(f"products/{p.uid}", data)
    img = ProductImage(product_id=p.id, url=url, storage_path=path, alt=p.name,
                       is_main=count == 0, sort_order=count)
    db.add(img)
    db.commit()
    return img


@router.patch("/products/{pid}/images/{iid}/main", response_model=list[ImageOut])
def set_main_image(pid: UUID, iid: int, db: Session = Depends(get_db)):
    p = _load(db, pid)
    if not any(i.id == iid for i in p.images):
        _nf("Image")
    for i in p.images:
        i.is_main = i.id == iid
    db.commit()
    return p.images


@router.delete("/products/{pid}/images/{iid}", status_code=204)
async def delete_image(pid: UUID, iid: int, db: Session = Depends(get_db)):
    p = _load(db, pid)
    img = next((i for i in p.images if i.id == iid), None) or _nf("Image")
    was_main, path = img.is_main, img.storage_path
    db.delete(img)
    db.flush()
    remaining = [i for i in p.images if i.id != iid]
    if was_main and remaining:  # never leave a product without a main image
        remaining[0].is_main = True
    db.commit()
    await storage.delete(path)
