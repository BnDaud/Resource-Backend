from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_token
from app.models import Role, Staff

COOKIE = "rc_session"
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def get_current_staff(request: Request, db: Session = Depends(get_db)) -> Staff:
    token = request.cookies.get(COOKIE)
    payload = decode_token(token) if token else None
    if not payload:
        raise HTTPException(401, "Not signed in")
    # Cross-site forms cannot add custom headers, so this blocks CSRF alongside SameSite cookies.
    if request.method in UNSAFE and request.headers.get("x-requested-with") != "rc-cms":
        raise HTTPException(403, "Missing request header")
    staff = db.get(Staff, int(payload["sub"]))
    if not staff or not staff.is_active:
        raise HTTPException(401, "Account disabled or removed")
    return staff


def require_admin(staff: Staff = Depends(get_current_staff)) -> Staff:
    if staff.role != Role.admin:
        raise HTTPException(403, "Admin access required")
    return staff
