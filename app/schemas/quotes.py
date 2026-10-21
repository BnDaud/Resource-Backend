from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models import (
    CustomerType,
    QuoteStatus,
)
from app.schemas.common import ORM, check_phone, clean


class QuoteItemIn(BaseModel):
    product_id: UUID  # the product's public id
    quantity: int = Field(ge=1, le=100000)
    note: str = Field(default="", max_length=300)


class QuoteIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    customer_type: CustomerType
    phone: str
    email: EmailStr | None = None
    company: str = Field(default="", max_length=160)
    message: str = Field(default="", max_length=3000)
    preferred_contact: str = Field(default="", pattern=r"^(|phone|whatsapp|email)$")
    items: list[QuoteItemIn] = Field(min_length=1, max_length=100)
    website: str = Field(default="", max_length=200)  # honeypot: must stay empty

    _phone = field_validator("phone")(check_phone)

    @field_validator("full_name", "company")
    @classmethod
    def _ws(cls, v: str) -> str:
        return clean(v)


class QuoteItemOut(ORM):
    id: int
    product_id: str | None = Field(validation_alias="product_uid")
    product_name: str
    product_sku: str
    spec_note: str
    quantity: int


class QuoteCreated(BaseModel):
    reference: str
    message: str = "Your quote request has been received. We will contact you shortly."


class QuoteOut(ORM):
    id: str = Field(validation_alias="uid")
    reference: str
    full_name: str
    customer_type: CustomerType
    phone: str
    email: str
    company: str
    message: str
    preferred_contact: str
    status: QuoteStatus
    internal_notes: str
    created_at: datetime
    items: list[QuoteItemOut]


class QuoteListItem(ORM):
    id: str = Field(validation_alias="uid")
    reference: str
    full_name: str
    customer_type: CustomerType
    phone: str
    status: QuoteStatus
    created_at: datetime
    item_count: int = 0


class QuoteUpdate(BaseModel):
    status: QuoteStatus | None = None
    internal_notes: str | None = Field(default=None, max_length=5000)
