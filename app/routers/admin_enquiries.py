from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.crypto import query_tokens
from app.core.db import get_db
from app.deps import get_current_staff
from app.models import (
    Enquiry,
    EnquiryStatus,
)
from app.schemas import (
    EnquiryOut,
    EnquiryUpdate,
    Page,
)
from app.services.common import page_count

router = APIRouter(prefix="/api/v1/admin", tags=["admin-enquiries"])
auth = [Depends(get_current_staff)]

@router.get("/enquiries", response_model=Page[EnquiryOut], dependencies=auth)
def list_enquiries(
    db: Session = Depends(get_db),
    q: str | None = Query(None, max_length=100),
    status: EnquiryStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    stmt = select(Enquiry)
    if status:
        stmt = stmt.where(Enquiry.status == status)
    if q and q.strip():
        toks = [Enquiry.search_tokens.contains(t) for t in query_tokens(q)]
        stmt = stmt.where(or_(*toks) if toks else Enquiry.id < 0)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Enquiry.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=rows, total=total, page=page, page_size=page_size, pages=page_count(total, page_size))


@router.patch("/enquiries/{eid}", response_model=EnquiryOut, dependencies=auth)
def update_enquiry(eid: UUID, data: EnquiryUpdate, db: Session = Depends(get_db)):
    e = db.scalar(select(Enquiry).where(Enquiry.uid == str(eid)))
    if not e:
        raise HTTPException(404, "Enquiry not found")
    if data.status is not None:
        e.status = data.status
    if data.internal_notes is not None:
        e.internal_notes = data.internal_notes
    db.commit()
    return e
