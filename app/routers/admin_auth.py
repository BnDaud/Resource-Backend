from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import blind_index
from app.core.db import get_db
from app.core.limiter import limiter
from app.core.security import create_token, hash_password, verify_password
from app.deps import COOKIE, get_current_staff
from app.models import Staff
from app.schemas import LoginIn, PasswordChange, StaffOut

router = APIRouter(prefix="/api/v1/admin/auth", tags=["admin-auth"])

# Hash compared when the email is unknown, so response time does not reveal which emails exist.
_DUMMY = hash_password("not-a-real-password")


@router.post("/login", response_model=StaffOut)
@limiter.limit("8/minute")
def login(request: Request, data: LoginIn, response: Response, db: Session = Depends(get_db)):
    staff = db.scalar(select(Staff).where(Staff.email_hash == blind_index(data.email)))
    ok = verify_password(data.password, staff.password_hash if staff else _DUMMY)
    if not staff or not ok or not staff.is_active:
        raise HTTPException(401, "Incorrect email or password")
    s = get_settings()
    response.set_cookie(
        COOKIE, create_token(staff.id, staff.role.value), max_age=s.jwt_expire_minutes * 60,
        httponly=True, secure=s.cookie_secure, samesite="lax", path="/",
    )
    return staff


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")


@router.get("/me", response_model=StaffOut)
def me(staff: Staff = Depends(get_current_staff)):
    return staff


@router.post("/change-password", status_code=204)
def change_password(data: PasswordChange, staff: Staff = Depends(get_current_staff), db: Session = Depends(get_db)):
    if not verify_password(data.current_password, staff.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    staff.password_hash = hash_password(data.new_password)
    db.commit()
