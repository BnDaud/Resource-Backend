from datetime import date, datetime, time, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.crypto import query_tokens
from app.core.db import get_db
from app.deps import get_current_staff
from app.models import QuoteItem, QuoteRequest, QuoteStatus
from app.schemas import (
    Page,
    QuoteListItem,
    QuoteOut,
    QuoteUpdate,
)
from app.services.common import escape_like, page_count

router = APIRouter(prefix="/api/v1/admin", tags=["admin-quotes"])
auth = [Depends(get_current_staff)]

@router.get("/quotes", response_model=Page[QuoteListItem], dependencies=auth)
def list_quotes(
    db: Session = Depends(get_db),
    q: str | None = Query(None, max_length=100),
    status: QuoteStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    stmt = select(QuoteRequest)
    if status:
        stmt = stmt.where(QuoteRequest.status == status)
    if date_from:
        stmt = stmt.where(QuoteRequest.created_at >= datetime.combine(date_from, time.min, timezone.utc))
    if date_to:
        stmt = stmt.where(QuoteRequest.created_at <= datetime.combine(date_to, time.max, timezone.utc))
    if q and q.strip():
        like = f"%{escape_like(q.strip())}%"
        # Names, phones and notes are encrypted, so they are matched through blind indexes (whole words / full numbers).
        toks = [QuoteRequest.search_tokens.contains(t) for t in query_tokens(q)]
        stmt = stmt.where(or_(QuoteRequest.reference.ilike(like, escape="\\"), *toks))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.options(selectinload(QuoteRequest.items)).order_by(QuoteRequest.created_at.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    items = [QuoteListItem.model_validate(r).model_copy(update={"item_count": len(r.items)}) for r in rows]
    return Page(items=items, total=total, page=page, page_size=page_size, pages=page_count(total, page_size))


def _quote(db: Session, qid: UUID) -> QuoteRequest:
    q = db.scalar(select(QuoteRequest).where(QuoteRequest.uid == str(qid)).options(joinedload(QuoteRequest.items).joinedload(QuoteItem.product)))
    if not q:
        raise HTTPException(404, "Quote request not found")
    return q


@router.get("/quotes/{qid}", response_model=QuoteOut, dependencies=auth)
def get_quote(qid: UUID, db: Session = Depends(get_db)):
    return _quote(db, qid)


@router.patch("/quotes/{qid}", response_model=QuoteOut, dependencies=auth)
def update_quote(qid: UUID, data: QuoteUpdate, db: Session = Depends(get_db)):
    q = _quote(db, qid)
    if data.status is not None:
        q.status = data.status
    if data.internal_notes is not None:
        q.internal_notes = data.internal_notes
    db.commit()
    return q
