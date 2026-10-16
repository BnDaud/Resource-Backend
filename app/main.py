from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import get_settings
from app.core.limiter import limiter
from app.routers import (
    admin_auth,
    admin_categories,
    admin_dashboard,
    admin_enquiries,
    admin_products,
    admin_quotes,
    admin_settings,
    admin_staff,
    admin_testimonials,
    public,
    seo,
)

settings = get_settings()
prod = settings.environment == "production"

app = FastAPI(
    title="Resources Components API", version="1.0.0",
    docs_url=None if prod else "/docs", redoc_url=None, openapi_url=None if prod else "/openapi.json",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type", "X-Requested-With"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    if request.url.path.startswith("/api/v1/admin"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    return JSONResponse({"detail": "Something went wrong. Please try again."}, status_code=500)


@app.get("/health")
def health():
    return {"status": "ok"}


for r in (
    public.router, admin_auth.router, admin_categories.router, admin_products.router, admin_dashboard.router, admin_quotes.router,
    admin_enquiries.router, admin_testimonials.router, seo.router, admin_settings.router, admin_staff.router,
):
    app.include_router(r)
