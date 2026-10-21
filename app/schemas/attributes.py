import re

from pydantic import BaseModel, Field, field_validator

from app.models import Section
from app.schemas.common import ORM, clean

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class OptionIn(BaseModel):
    id: int | None = None
    label: str = Field(min_length=1, max_length=60)
    color: str | None = None  # swatch shown beside the label

    @field_validator("label")
    @classmethod
    def _label(cls, v: str) -> str:
        v = clean(v)
        if not v:
            raise ValueError("Enter a name for the option")
        return v

    @field_validator("color")
    @classmethod
    def _color(cls, v: str | None) -> str | None:
        if not v:
            return None
        if not HEX.match(v):
            raise ValueError("Colour must look like #c0392b")
        return v.lower()


class AttributeIn(BaseModel):
    id: int | None = None
    name: str = Field(min_length=1, max_length=60)
    filterable: bool = True
    customer_picks: bool = True
    options: list[OptionIn] = Field(default_factory=list, max_length=60)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = clean(v)
        if not v:
            raise ValueError("Enter a name")
        return v

    @field_validator("options")
    @classmethod
    def _unique_labels(cls, v: list[OptionIn]) -> list[OptionIn]:
        seen = set()
        for o in v:
            if o.label.lower() in seen:
                raise ValueError(f"'{o.label}' is listed twice")
            seen.add(o.label.lower())
        return v


class OptionOut(ORM):
    id: int
    label: str
    color: str | None


class AttributeOut(ORM):
    id: int
    name: str
    filterable: bool
    customer_picks: bool
    section: Section | None
    category_id: int | None
    options: list[OptionOut]


class ProductAttribute(BaseModel):
    """One attribute of a product with the options that product has."""
    id: int
    name: str
    customer_picks: bool
    options: list[OptionOut]
