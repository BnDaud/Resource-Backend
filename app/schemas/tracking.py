from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import check_phone


class TrackIn(BaseModel):
    reference: str = Field(min_length=6, max_length=24)
    phone: str

    _phone = field_validator("phone")(check_phone)


class TrackItem(BaseModel):
    name: str
    sku: str
    quantity: int
    note: str = ""


class TrackOut(BaseModel):
    """What a customer may see. Internal notes and contact details are never included."""

    reference: str
    kind: Literal["quote", "enquiry"]
    status: str
    created_at: datetime
    subject: str = ""
    items: list[TrackItem] = []
