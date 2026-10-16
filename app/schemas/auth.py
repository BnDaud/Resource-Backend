
from pydantic import BaseModel, EmailStr, Field

from app.models import (
    Role,
)
from app.schemas.common import ORM, Page, check_phone, clean  # noqa: F401


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class StaffOut(ORM):
    id: int
    email: str
    name: str
    role: Role
    is_active: bool


class StaffCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=10, max_length=128)
    role: Role = Role.editor


class StaffUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=10, max_length=128)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)
