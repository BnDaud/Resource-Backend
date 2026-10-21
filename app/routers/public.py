import math

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.crypto import phone_tokens
from app.core.db import get_db
from app.core.limiter import limiter
from app.models import (
    Availability,
    Category,
    Enquiry,
    Product,
    ProductImage,
    QuoteRequest,
    Section,
    Testimonial,
)
from app.schemas import (
    AvailabilityOut,
    CategoryPublic,
    EnquiryIn,
    Page,
    ProductPublic,
    ProductPublicDetail,
    QuoteCreated,
    QuoteIn,
    TrackIn,
    TrackItem,
    TrackOut,
    SettingsIO,
    TestimonialPublic,
)
from app.services.common import escape_like, get_site_settings
from app.services.quotes import create_quote

router = APIRouter(prefix="/api/v1", tags=["public"])


def _main(p: Product) -> str | None:
    if not p.images:
        return None
    return next((i.url for i in p.images if i.is_main), p.images[0].url)


def to_public(p: Product) -> dict:
    return {
        "uid": p.uid, "name": p.name, "slug": p.slug, "sku": p.sku, "category_id": p.category_id,
        "category_name": p.category.name, "brand": p.brand, "short_description": p.short_description,
        "availability": p.availability, "price_mode": p.price_mode,
        "public_price": p.public_price if p.price_mode.value == "public" else None,
        "is_featured": p.is_featured, "is_new": p.is_new, "main_image": _main(p), "created_at": p.created_at,
    }


def to_detail(p: Product) -> dict:
    return {
        **to_public(p), "description": p.description, "sizes": p.sizes or [], "colours": p.colours or [],
        "specs": p.specs, "images": p.images, "category_slug": p.category.slug,
    }


def cache(response: Response, seconds: int = 60):
    response.headers["Cache-Control"] = f"public, max-age={seconds}"


@router.get("/categories", response_model=list[CategoryPublic])
def categories(response: Response, db: Session = Depends(get_db)):
    cache(response)
    counts = dict(
        db.execute(
            select(Product.category_id, func.count()).where(Product.is_archived.is_(False)).group_by(Product.category_id)
        ).all()
    )
    covers: dict[int, str] = {}  # first main image per category, featured and newest products first
    for cid, url in db.execute(
        select(Product.category_id, ProductImage.url).join(ProductImage)
        .where(Product.is_archived.is_(False), ProductImage.is_main.is_(True))
        .order_by(Product.is_featured.desc(), Product.created_at.desc())
    ):
        covers.setdefault(cid, url)
    rows = db.scalars(select(Category).order_by(Category.sort_order, Category.name)).all()
    return [
        CategoryPublic.model_validate(c).model_copy(update={"product_count": counts.get(c.id, 0), "cover_image": covers.get(c.id)})
        for c in rows
    ]


@router.get("/products", response_model=Page[ProductPublic])
def products(
    response: Response,
    db: Session = Depends(get_db),
    q: str | None = Query(None, max_length=100),
    category: str | None = Query(None, max_length=140, description="category slug"),
    section: Section | None = Query(None, description="boards or accessories"),
    availability: list[Availability] | None = Query(None),
    featured: bool | None = None,
    new: bool | None = None,
    sort: str = Query("relevance", pattern="^(relevance|newest|alpha)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=48),
):
    cache(response, 30)
    stmt = select(Product).where(Product.is_archived.is_(False))
    if category or section:
        stmt = stmt.join(Category)
    if category:
        stmt = stmt.where(Category.slug == category)
    if section:
        stmt = stmt.where(Category.section == section)
    if availability:
        stmt = stmt.where(Product.availability.in_(availability))
    if featured is not None:
        stmt = stmt.where(Product.is_featured.is_(featured))
    if new is not None:
        stmt = stmt.where(Product.is_new.is_(new))
    order = [Product.name]
    if q and q.strip():
        like = f"%{escape_like(q.strip())}%"
        strong = or_(Product.name.ilike(like, escape="\\"), Product.sku.ilike(like, escape="\\"))
        weak = or_(
            Product.brand.ilike(like, escape="\\"), Product.short_description.ilike(like, escape="\\"),
            Product.description.ilike(like, escape="\\"),
        )
        stmt = stmt.where(or_(strong, weak))
        if sort == "relevance":
            order = [case((strong, 0), else_=1), Product.name]
    if sort == "newest":
        order = [Product.created_at.desc(), Product.id.desc()]
    elif sort == "alpha":
        order = [Product.name]
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.options(selectinload(Product.images), joinedload(Product.category))
        .order_by(*order).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return Page(items=[to_public(p) for p in rows], total=total, page=page, page_size=page_size,
                pages=max(1, math.ceil(total / page_size)))


def _get_public_product(db: Session, slug: str) -> Product:
    p = db.scalar(
        select(Product).where(Product.slug == slug, Product.is_archived.is_(False))
        .options(selectinload(Product.images), selectinload(Product.specs), joinedload(Product.category))
    )
    if not p:
        raise HTTPException(404, "Product not found")
    return p


@router.get("/products/{slug}", response_model=ProductPublicDetail)
def product_detail(slug: str, response: Response, db: Session = Depends(get_db)):
    cache(response, 30)
    return to_detail(_get_public_product(db, slug))


@router.get("/products/{slug}/availability", response_model=AvailabilityOut)
def product_availability(slug: str, db: Session = Depends(get_db)):
    p = _get_public_product(db, slug)
    return AvailabilityOut(id=p.uid, sku=p.sku, availability=p.availability)


@router.get("/products/{slug}/related", response_model=list[ProductPublic])
def related(slug: str, db: Session = Depends(get_db)):
    p = _get_public_product(db, slug)
    rows = db.scalars(
        select(Product).where(Product.category_id == p.category_id, Product.id != p.id, Product.is_archived.is_(False))
        .options(selectinload(Product.images), joinedload(Product.category)).order_by(Product.created_at.desc()).limit(4)
    ).all()
    return [to_public(x) for x in rows]


@router.post("/quotes", response_model=QuoteCreated, status_code=201)
@limiter.limit("10/hour")
def submit_quote(request: Request, data: QuoteIn, db: Session = Depends(get_db)):
    if data.website:  # honeypot tripped: pretend success, store nothing
        return QuoteCreated(reference="RC-PENDING")
    return QuoteCreated(reference=create_quote(db, data).reference)


@router.post("/enquiries", status_code=201)
@limiter.limit("10/hour")
def submit_enquiry(request: Request, data: EnquiryIn, db: Session = Depends(get_db)):
    message = "Thank you. We have received your message and will reply soon."
    if data.website:  # honeypot tripped: pretend success, store nothing
        return {"message": message, "reference": "EN-PENDING"}
    enquiry = Enquiry(name=data.name, email=data.email or "", phone=data.phone, subject=data.subject, message=data.message)
    db.add(enquiry)
    db.commit()
    return {"message": message, "reference": enquiry.reference}


@router.post("/track", response_model=TrackOut)
@limiter.limit("20/hour")
def track(request: Request, data: TrackIn, db: Session = Depends(get_db)):
    """Customer lookup by reference AND phone. Any mismatch gives the same 404, so references cannot be probed."""
    ref = data.reference.strip().upper()
    model = QuoteRequest if ref.startswith("RC-") else Enquiry if ref.startswith("EN-") else None
    row = db.scalar(select(model).where(model.reference == ref)) if model else None
    wanted = phone_tokens(data.phone)
    if not row or not any(t in row.search_tokens.split() for t in wanted):
        raise HTTPException(404, "We could not find a request with those details. Check the reference and phone number.")
    if isinstance(row, QuoteRequest):
        items = [TrackItem(name=i.product_name, sku=i.product_sku, quantity=i.quantity, note=i.spec_note) for i in row.items]
        return TrackOut(reference=row.reference, kind="quote", status=row.status.value, created_at=row.created_at, items=items)
    return TrackOut(reference=row.reference, kind="enquiry", status=row.status.value, created_at=row.created_at, subject=row.subject)


@router.get("/testimonials", response_model=list[TestimonialPublic])
def testimonials(response: Response, db: Session = Depends(get_db)):
    cache(response)
    return db.scalars(select(Testimonial).where(Testimonial.is_published.is_(True)).order_by(Testimonial.created_at.desc())).all()


@router.get("/settings", response_model=SettingsIO)
def public_settings(response: Response, db: Session = Depends(get_db)):
    cache(response)
    return get_site_settings(db)
