from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ORM, Page, check_phone, clean  # noqa: F401


class TestimonialIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=160)
    company: str = Field(default="", max_length=160)
    text: str = Field(min_length=5, max_length=2000)
    is_published: bool = False


class TestimonialOut(ORM):
    id: int
    display_name: str
    company: str
    text: str
    image_url: str | None
    is_published: bool
    created_at: datetime


class TestimonialPublic(ORM):
    id: int
    display_name: str
    company: str
    text: str
    image_url: str | None

class SettingsIO(BaseModel):
    business_name: str = Field(max_length=160)
    address: str = Field(max_length=300)
    opening_hours: str = Field(default="", max_length=200)
    phone: str = Field(default="", max_length=40)
    email: str = Field(default="", max_length=254)
    whatsapp_number: str = Field(default="", pattern=r"^(\d{8,15})?$")
    whatsapp_message: str = Field(default="", max_length=300)
    instagram_url: str = Field(default="", max_length=300, pattern=r"^(https?://.*)?$")
    tiktok_url: str = Field(default="", max_length=300, pattern=r"^(https?://.*)?$")
    seo_title: str = Field(default="", max_length=160)
    seo_description: str = Field(default="", max_length=320)

    model_config = ConfigDict(from_attributes=True)
