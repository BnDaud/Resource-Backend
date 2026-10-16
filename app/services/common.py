import re
import secrets
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "item"


def unique_slug(db: Session, model, text: str, exclude_id: int | None = None) -> str:
    base = slugify(text)[:120]
    slug, n = base, 2
    while True:
        q = select(model.id).where(model.slug == slug)
        if exclude_id:
            q = q.where(model.id != exclude_id)
        if db.scalar(q) is None:
            return slug
        slug = f"{base}-{n}"
        n += 1


def escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_reference(now, prefix: str = "RC") -> str:
    """RC-YYMMDD-XXXX for quotes, EN-YYMMDD-XXXX for enquiries. Letters avoid look-alikes (no 0/O, 1/I)."""
    return f"{prefix}-{now:%y%m%d}-" + "".join(secrets.choice(_ALPHABET) for _ in range(4))


def get_site_settings(db):
    from app.models import SiteSettings

    row = db.get(SiteSettings, 1)
    if not row:
        row = SiteSettings(id=1)
        db.add(row)
        db.commit()
    return row


def page_count(total: int, size: int) -> int:
    import math

    return max(1, math.ceil(total / size))
