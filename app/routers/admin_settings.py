
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.deps import get_current_staff, require_admin
from app.schemas import (
    SettingsIO,
)
from app.services.common import get_site_settings

router = APIRouter(prefix="/api/v1/admin", tags=["admin-settings"])
auth = [Depends(get_current_staff)]

@router.get("/settings", response_model=SettingsIO, dependencies=auth)
def get_settings_admin(db: Session = Depends(get_db)):
    return get_site_settings(db)


@router.put("/settings", response_model=SettingsIO, dependencies=[Depends(require_admin)])
def put_settings(data: SettingsIO, db: Session = Depends(get_db)):
    s = get_site_settings(db)
    for k, v in data.model_dump().items():
        setattr(s, k, v)
    db.commit()
    return s
