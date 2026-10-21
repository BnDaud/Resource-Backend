from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models import (
    EnquiryStatus,
)
from app.schemas.common import ORM, check_phone, clean


class EnquiryIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr | None = None
    phone: str
    subject: str = Field(min_length=2, max_length=200)
    message: str = Field(min_length=5, max_length=5000)
    website: str = Field(default="", max_length=200)  # honeypot

    _phone = field_validator("phone")(check_phone)

    @field_validator("name", "subject")
    @classmethod
    def _ws(cls, v: str) -> str:
        return clean(v)


class EnquiryOut(ORM):
    id: str = Field(validation_alias="uid")
    reference: str
    name: str
    email: str
    phone: str
    subject: str
    message: str
    status: EnquiryStatus
    internal_notes: str
    created_at: datetime


class EnquiryUpdate(BaseModel):
    status: EnquiryStatus | None = None
    internal_notes: str | None = Field(default=None, max_length=5000)
