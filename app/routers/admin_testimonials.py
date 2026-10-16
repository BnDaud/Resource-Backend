
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.deps import get_current_staff
from app.models import (
    Testimonial,
)
from app.schemas import (
    TestimonialIn,
    TestimonialOut,
)
from app.services import storage

router = APIRouter(prefix="/api/v1/admin", tags=["admin-testimonials"])
auth = [Depends(get_current_staff)]

@router.get("/testimonials", response_model=list[TestimonialOut], dependencies=auth)
def list_testimonials(db: Session = Depends(get_db)):
    return db.scalars(select(Testimonial).order_by(Testimonial.created_at.desc())).all()


@router.post("/testimonials", response_model=TestimonialOut, status_code=201, dependencies=auth)
def create_testimonial(data: TestimonialIn, db: Session = Depends(get_db)):
    t = Testimonial(**data.model_dump())
    db.add(t)
    db.commit()
    return t


def _t(db: Session, tid: int) -> Testimonial:
    t = db.get(Testimonial, tid)
    if not t:
        raise HTTPException(404, "Testimonial not found")
    return t


@router.put("/testimonials/{tid}", response_model=TestimonialOut, dependencies=auth)
def update_testimonial(tid: int, data: TestimonialIn, db: Session = Depends(get_db)):
    t = _t(db, tid)
    for k, v in data.model_dump().items():
        setattr(t, k, v)
    db.commit()
    return t


@router.delete("/testimonials/{tid}", status_code=204, dependencies=auth)
def delete_testimonial(tid: int, db: Session = Depends(get_db)):
    db.delete(_t(db, tid))
    db.commit()


@router.post("/testimonials/{tid}/image", response_model=TestimonialOut, dependencies=auth)
async def testimonial_image(tid: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    t = _t(db, tid)
    data = await storage.read_and_optimise(file)
    _, url = await storage.upload("testimonials", data)
    t.image_url = url
    db.commit()
    return t
