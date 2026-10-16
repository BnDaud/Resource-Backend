from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models import Product

router = APIRouter(tags=["seo"])

STATIC_PAGES = ["/", "/products", "/contact", "/track", "/quote"]


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap(db: Session = Depends(get_db)):
    """Public pages and every active product. Admin and customer data are never listed."""
    s = get_settings()
    base = (s.site_url or s.allowed_origins[0]).rstrip("/")
    urls = [f"<url><loc>{escape(base + p)}</loc></url>" for p in STATIC_PAGES]
    for slug, updated in db.execute(select(Product.slug, Product.updated_at).where(Product.is_archived.is_(False))):
        urls.append(f"<url><loc>{escape(f'{base}/products/{slug}')}</loc><lastmod>{updated:%Y-%m-%d}</lastmod></url>")
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(urls) + "</urlset>"
    return Response(xml, media_type="application/xml", headers={"Cache-Control": "public, max-age=3600"})
