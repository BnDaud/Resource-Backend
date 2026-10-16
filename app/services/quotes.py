from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Product, QuoteItem, QuoteRequest
from app.schemas import QuoteIn
from app.services.common import new_reference


def create_quote(db: Session, data: QuoteIn) -> QuoteRequest:
    # Merge duplicate lines so one product appears once.
    merged: dict[str, tuple[int, str]] = {}
    for it in data.items:
        key = str(it.product_id)
        qty, note = merged.get(key, (0, ""))
        merged[key] = (qty + it.quantity, note or it.note)
    products = {
        p.uid: p for p in db.scalars(select(Product).where(Product.uid.in_(merged), Product.is_archived.is_(False)))
    }
    missing = [pid for pid in merged if pid not in products]
    if missing:
        raise HTTPException(422, "Some products are no longer available. Remove them from your list and try again.")
    for pid, (qty, _) in merged.items():
        if qty > 100000:
            raise HTTPException(422, "Quantity is too large")

    for _ in range(5):
        quote = QuoteRequest(
            reference=new_reference(datetime.now(timezone.utc)),
            full_name=data.full_name,
            customer_type=data.customer_type,
            phone=data.phone,
            email=data.email or "",
            company=data.company,
            message=data.message,
            preferred_contact=data.preferred_contact,
            items=[
                QuoteItem(  # snapshot: survives later renames, archiving or deletion
                    product_id=products[pid].id,
                    product_name=products[pid].name,
                    product_sku=products[pid].sku,
                    spec_note=note,
                    quantity=qty,
                )
                for pid, (qty, note) in merged.items()
            ],
        )
        db.add(quote)
        try:
            db.commit()
            return quote
        except IntegrityError:  # reference collision: retry with a new one
            db.rollback()
    raise HTTPException(500, "Could not create a reference number. Please try again.")
