import re
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models import (
    Availability,
    PriceMode,
)
from app.schemas.common import ORM, Page, check_phone, clean  # noqa: F401


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    sort_order: int = 0


class CategoryOut(ORM):
    id: int
    name: str
    slug: str
    description: str
    image_url: str | None
    sort_order: int


class CategoryPublic(CategoryOut):
    product_count: int = 0
    cover_image: str | None = None  # main image of a representative product

class ImageOut(ORM):
    id: int
    url: str
    alt: str
    is_main: bool
    sort_order: int


class SpecIO(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=300)


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sku: str = Field(min_length=1, max_length=64)
    category_id: int
    brand: str = Field(default="", max_length=120)
    short_description: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=10000)
    sizes: list[str] = Field(default_factory=list, max_length=50)
    colours: list[str] = Field(default_factory=list, max_length=50)
    specs: list[SpecIO] = Field(default_factory=list, max_length=50)
    availability: Availability = Availability.on_request
    price_mode: PriceMode = PriceMode.request
    public_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    wholesale_note: str = Field(default="", max_length=300)
    stock_qty: int | None = Field(default=None, ge=0)
    is_featured: bool = False
    is_new: bool = False

    @field_validator("sku")
    @classmethod
    def _sku(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.match(r"^[A-Z0-9][A-Z0-9._\-/]*$", v):
            raise ValueError("SKU may contain letters, numbers and . _ - /")
        return v

    @field_validator("name", "brand", "short_description")
    @classmethod
    def _ws(cls, v: str) -> str:
        return clean(v)

    @field_validator("sizes", "colours")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        out = []
        for x in v:
            x = clean(x)[:60]
            if x and x not in out:
                out.append(x)
        return out

    @model_validator(mode="after")
    def _price(self):
        if self.price_mode == PriceMode.public and self.public_price is None:
            raise ValueError("Enter a public price or choose 'Request price'")
        if self.price_mode == PriceMode.request:
            self.public_price = None
        return self


class SpecOut(ORM):
    name: str
    value: str


class ProductPublic(ORM):
    id: str = Field(validation_alias="uid")  # UUID; the integer primary key is never exposed
    name: str
    slug: str
    sku: str
    category_id: int
    category_name: str
    brand: str
    short_description: str
    availability: Availability
    price_mode: PriceMode
    public_price: Decimal | None
    is_featured: bool
    is_new: bool
    main_image: str | None
    created_at: datetime


class ProductPublicDetail(ProductPublic):
    description: str
    sizes: list[str]
    colours: list[str]
    specs: list[SpecOut]
    images: list[ImageOut]
    category_slug: str


class ProductAdmin(ProductPublicDetail):
    wholesale_note: str
    stock_qty: int | None
    is_archived: bool
    updated_at: datetime


class AvailabilityOut(BaseModel):
    id: str
    sku: str
    availability: Availability
