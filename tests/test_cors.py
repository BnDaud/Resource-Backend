from app.core.config import Settings

VERCEL = "https://project-uxn0h.vercel.app"


def preflight(client, origin):
    return client.options("/api/v1/products", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})


def test_origins_are_split_and_trailing_slashes_removed():
    s = Settings(database_url="x", jwt_secret="x", encryption_keys="x", blind_index_key="x",
                 frontend_origin=f"http://localhost:5173, {VERCEL}/")
    assert s.allowed_origins == ["http://localhost:5173", VERCEL]


def test_both_configured_origins_are_allowed_with_cookies(client):
    for origin in ("http://localhost:5173", VERCEL):
        r = preflight(client, origin)
        assert r.status_code == 200, origin
        assert r.headers["access-control-allow-origin"] == origin
        assert r.headers["access-control-allow-credentials"] == "true"  # the admin login cookie needs this


def test_other_origins_are_refused(client):
    for origin in ("https://evil.example", "https://project-uxn0h.vercel.app.evil.example", "http://project-uxn0h.vercel.app"):
        assert "access-control-allow-origin" not in preflight(client, origin).headers, origin
