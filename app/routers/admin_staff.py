
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import blind_index
from app.core.db import get_db
from app.core.security import hash_password
from app.deps import get_current_staff, require_admin
from app.models import (
    Role,
    Staff,
)
from app.schemas import (
    StaffCreate,
    StaffOut,
    StaffUpdate,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin-staff"])
auth = [Depends(get_current_staff)]

@router.get("/staff", response_model=list[StaffOut], dependencies=[Depends(require_admin)])
def list_staff(db: Session = Depends(get_db)):
    return db.scalars(select(Staff).order_by(Staff.name)).all()


@router.post("/staff", response_model=StaffOut, status_code=201, dependencies=[Depends(require_admin)])
def create_staff(data: StaffCreate, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.scalar(select(Staff.id).where(Staff.email_hash == blind_index(email))):
        raise HTTPException(409, "A staff account with this email already exists")
    s = Staff(email=email, name=data.name, role=data.role, password_hash=hash_password(data.password))
    db.add(s)
    db.commit()
    return s


@router.patch("/staff/{sid}", response_model=StaffOut)
def update_staff(sid: int, data: StaffUpdate, me: Staff = Depends(require_admin), db: Session = Depends(get_db)):
    s = db.get(Staff, sid)
    if not s:
        raise HTTPException(404, "Staff account not found")
    if s.id == me.id and (data.is_active is False or (data.role and data.role != Role.admin)):
        raise HTTPException(400, "You cannot disable or demote your own account")
    if data.name is not None:
        s.name = data.name
    if data.role is not None:
        s.role = data.role
    if data.is_active is not None:
        s.is_active = data.is_active
    if data.password:
        s.password_hash = hash_password(data.password)
    db.commit()
    return s
