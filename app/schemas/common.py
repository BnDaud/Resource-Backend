import re
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s\-()]{5,23}$")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


def clean(v: str) -> str:
    return " ".join(v.split()) if v else ""


def check_phone(v: str) -> str:
    v = v.strip()
    if not PHONE_RE.match(v):
        raise ValueError("Enter a valid phone number")
    return v
