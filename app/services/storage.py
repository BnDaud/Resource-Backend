import io
import uuid

import httpx
from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings

ALLOWED = {"JPEG", "PNG", "WEBP"}
MAX_SIDE = 2000


def _headers() -> dict:
    key = get_settings().supabase_service_role_key
    return {"Authorization": f"Bearer {key}", "apikey": key}


async def read_and_optimise(file: UploadFile, max_side: int = MAX_SIDE) -> bytes:
    """Validate the upload is a real image, strip metadata, cap size, re-encode as WebP."""
    s = get_settings()
    data = await file.read(s.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Image must be {s.max_upload_mb} MB or smaller")
    try:
        img = Image.open(io.BytesIO(data))
        if img.format not in ALLOWED:
            raise HTTPException(415, "Only JPG, PNG or WebP images are allowed")
        img.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(415, "File is not a valid image")
    img = img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB")
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, "WEBP", quality=85, method=4)
    return out.getvalue()


def public_url(path: str) -> str:
    s = get_settings()
    return f"{s.supabase_url}/storage/v1/object/public/{s.supabase_bucket}/{path}"


async def upload(folder: str, data: bytes) -> tuple[str, str]:
    s = get_settings()
    path = f"{folder}/{uuid.uuid4().hex}.webp"
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{s.supabase_url}/storage/v1/object/{s.supabase_bucket}/{path}",
            headers={**_headers(), "Content-Type": "image/webp", "x-upsert": "false"},
            content=data,
        )
    if r.status_code >= 300:
        raise HTTPException(502, "Image storage is unavailable. Try again shortly.")
    return path, public_url(path)


async def delete(path: str) -> None:
    """Best effort: a failed storage delete must not block the database change."""
    s = get_settings()
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            await c.delete(f"{s.supabase_url}/storage/v1/object/{s.supabase_bucket}/{path}", headers=_headers())
    except httpx.HTTPError:
        pass
