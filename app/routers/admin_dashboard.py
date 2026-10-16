
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.deps import get_current_staff
from app.models import (
    Availability,
    Category,
    Enquiry,
    EnquiryStatus,
    Product,
    QuoteRequest,
    QuoteStatus,
    Testimonial,
)
from app.schemas import (
    EnquiryOut,
    QuoteListItem,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin-dashboard"])
auth = [Depends(get_current_staff)]

@router.get("/dashboard", dependencies=auth)
def dashboard(db: Session = Depends(get_db)):
    cnt = lambda stmt: db.scalar(stmt) or 0  # noqa: E731
    recent = db.scalars(select(Enquiry).order_by(Enquiry.created_at.desc()).limit(5)).all()
    recent_q = db.scalars(select(QuoteRequest).order_by(QuoteRequest.created_at.desc()).limit(5)).all()
    return {
        "total_products": cnt(select(func.count()).select_from(Product).where(Product.is_archived.is_(False))),
        "total_categories": cnt(select(func.count()).select_from(Category)),
        "new_enquiries": cnt(select(func.count()).select_from(Enquiry).where(Enquiry.status == EnquiryStatus.new)),
        "outstanding_quotes": cnt(select(func.count()).select_from(QuoteRequest).where(
            QuoteRequest.status.in_([QuoteStatus.new, QuoteStatus.under_review]))),
        "out_of_stock": cnt(select(func.count()).select_from(Product).where(
            Product.availability == Availability.out_of_stock, Product.is_archived.is_(False))),
        "published_testimonials": cnt(select(func.count()).select_from(Testimonial).where(Testimonial.is_published.is_(True))),
        "recent_quotes": [QuoteListItem.model_validate(q).model_copy(update={"item_count": len(q.items)}) for q in recent_q],
        "recent_enquiries": [EnquiryOut.model_validate(e) for e in recent],
    }
