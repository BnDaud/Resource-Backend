"""Create the public-read image bucket. Uploads only happen through the backend."""
import httpx

from app.core.config import get_settings

s = get_settings()
h = {"Authorization": f"Bearer {s.supabase_service_role_key}", "apikey": s.supabase_service_role_key}
r = httpx.post(
    f"{s.supabase_url}/storage/v1/bucket", headers=h, timeout=30,
    json={"id": s.supabase_bucket, "name": s.supabase_bucket, "public": True,
          "file_size_limit": s.max_upload_mb * 1024 * 1024,
          "allowed_mime_types": ["image/webp", "image/jpeg", "image/png"]},
)
print(r.status_code, r.text[:200])
