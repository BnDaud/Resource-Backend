from tests.conftest import H, login

PROD = {"name": "New Plywood", "sku": "pw-1", "category_id": 1, "availability": "available",
        "price_mode": "request", "wholesale_note": "internal", "stock_qty": 5,
        "specs": [{"name": "Thickness", "value": "18mm"}], "sizes": ["8x4", "8x4", " "], "colours": ["Oak"]}


def test_admin_endpoints_require_login(client, seed):
    for path in ["/dashboard", "/products", "/categories", "/quotes", "/enquiries", "/testimonials", "/settings", "/staff"]:
        assert client.get(f"/api/v1/admin{path}").status_code == 401, path
    assert client.get("/api/v1/admin/auth/me").status_code == 401


def test_login_logout_and_bad_credentials(client, seed):
    assert client.post("/api/v1/admin/auth/login", json={"email": "admin@test.com", "password": "wrong"}).status_code == 401
    assert client.post("/api/v1/admin/auth/login", json={"email": "nobody@test.com", "password": "wrong-pass-1"}).status_code == 401
    r = login(client)
    assert "httponly" in r.headers["set-cookie"].lower() and "samesite=lax" in r.headers["set-cookie"].lower()
    assert client.get("/api/v1/admin/auth/me").json()["email"] == "admin@test.com"
    client.post("/api/v1/admin/auth/logout")
    assert client.get("/api/v1/admin/auth/me").status_code == 401


def test_mutations_require_csrf_header(client, seed):
    login(client)
    assert client.post("/api/v1/admin/categories", json={"name": "X"}).status_code == 403
    assert client.post("/api/v1/admin/categories", json={"name": "X"}, headers=H).status_code == 201


def test_disabled_staff_locked_out(client, seed, db):
    login(client, "ed@test.com", "correct-horse-2")
    from app.core.crypto import blind_index
    from app.models import Staff
    db.query(Staff).filter_by(email_hash=blind_index("ed@test.com")).one().is_active = False
    db.commit()
    assert client.get("/api/v1/admin/auth/me").status_code == 401


def test_editor_cannot_manage_staff_or_settings(client, seed):
    login(client, "ed@test.com", "correct-horse-2")
    assert client.get("/api/v1/admin/staff").status_code == 403
    assert client.post("/api/v1/admin/staff", headers=H, json={"email": "n@t.com", "name": "N", "password": "longenough123"}).status_code == 403
    assert client.put("/api/v1/admin/settings", headers=H, json={"business_name": "x", "address": "y"}).status_code == 403
    assert client.get("/api/v1/admin/settings").status_code == 200  # read is allowed
    assert client.get("/api/v1/admin/products").status_code == 200


def test_admin_cannot_demote_self_and_creates_staff(client, seed):
    login(client)
    me = client.get("/api/v1/admin/auth/me").json()["id"]
    assert client.patch(f"/api/v1/admin/staff/{me}", headers=H, json={"role": "editor"}).status_code == 400
    assert client.patch(f"/api/v1/admin/staff/{me}", headers=H, json={"is_active": False}).status_code == 400
    r = client.post("/api/v1/admin/staff", headers=H, json={"email": "NEW@t.com", "name": "N", "password": "longenough123"})
    assert r.status_code == 201 and r.json()["email"] == "new@t.com" and "password" not in r.text
    assert client.post("/api/v1/admin/staff", headers=H, json={"email": "new@t.com", "name": "N", "password": "longenough123"}).status_code == 409
    assert client.post("/api/v1/admin/staff", headers=H, json={"email": "w@t.com", "name": "N", "password": "short"}).status_code == 422


def test_product_crud_validation_and_private_fields(client, seed):
    login(client)
    r = client.post("/api/v1/admin/products", json={**PROD, "category_id": seed["cat"].id}, headers=H)
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["sku"] == "PW-1" and p["slug"] == "new-plywood" and p["sizes"] == ["8x4"]
    assert p["wholesale_note"] == "internal" and p["stock_qty"] == 5  # staff see private fields
    pub = client.get("/api/v1/products/new-plywood").text
    assert "internal" not in pub and "stock_qty" not in pub
    # duplicate SKU
    assert client.post("/api/v1/admin/products", json={**PROD, "name": "Other", "category_id": seed["cat"].id}, headers=H).status_code == 409
    # public price mode needs a price; negative rejected; bad category rejected
    base = {**PROD, "sku": "PW-2", "name": "P2", "category_id": seed["cat"].id}
    assert client.post("/api/v1/admin/products", json={**base, "price_mode": "public"}, headers=H).status_code == 422
    assert client.post("/api/v1/admin/products", json={**base, "price_mode": "public", "public_price": -5}, headers=H).status_code == 422
    assert client.post("/api/v1/admin/products", json={**base, "category_id": 999}, headers=H).status_code == 422
    # edit + slug follows rename, archive hides from public
    pid = p["id"]
    up = client.put(f"/api/v1/admin/products/{pid}", json={**PROD, "name": "Marine Plywood", "category_id": seed["cat"].id,
                    "price_mode": "public", "public_price": "1999.50"}, headers=H).json()
    assert up["slug"] == "marine-plywood" and float(up["public_price"]) == 1999.5
    assert client.patch(f"/api/v1/admin/products/{pid}/archive", headers=H).json()["is_archived"] is True
    assert client.get("/api/v1/products/marine-plywood").status_code == 404
    assert client.get("/api/v1/admin/products", params={"archived": "true"}).json()["total"] >= 1


def test_category_rules(client, seed):
    login(client)
    assert client.post("/api/v1/admin/categories", json={"name": "flush doors"}, headers=H).status_code == 409
    assert client.delete(f"/api/v1/admin/categories/{seed['cat'].id}", headers=H).status_code == 409  # has products
    c = client.post("/api/v1/admin/categories", json={"name": "Brand New"}, headers=H).json()
    assert c["slug"] == "brand-new"
    assert client.delete(f"/api/v1/admin/categories/{c['id']}", headers=H).status_code == 204


def test_quote_management_and_dashboard(client, seed):
    ref = client.post("/api/v1/quotes", json={"full_name": "Ada Obi", "customer_type": "retail", "phone": "08012345678",
                      "items": [{"product_id": seed["p1"].uid, "quantity": 2}]}).json()["reference"]
    login(client)
    lst = client.get("/api/v1/admin/quotes", params={"q": ref}).json()
    assert lst["total"] == 1 and lst["items"][0]["item_count"] == 1
    assert client.get("/api/v1/admin/quotes", params={"q": "08012345678"}).json()["total"] == 1
    assert client.get("/api/v1/admin/quotes", params={"status": "closed"}).json()["total"] == 0
    qid = lst["items"][0]["id"]
    r = client.patch(f"/api/v1/admin/quotes/{qid}", json={"status": "quoted", "internal_notes": "called"}, headers=H)
    assert r.json()["status"] == "quoted" and r.json()["internal_notes"] == "called"
    assert client.patch(f"/api/v1/admin/quotes/{qid}", json={"status": "nonsense"}, headers=H).status_code == 422
    d = client.get("/api/v1/admin/dashboard").json()
    assert d["total_products"] == 2 and d["outstanding_quotes"] == 0 and d["out_of_stock"] == 1


def test_image_upload_rules(client, seed, monkeypatch):
    import io
    from PIL import Image
    from app.services import storage

    async def fake_upload(folder, data):
        return f"{folder}/x.webp", f"https://cdn/{folder}/x.webp"

    async def fake_delete(path):
        return None

    monkeypatch.setattr(storage, "upload", fake_upload)
    monkeypatch.setattr(storage, "delete", fake_delete)
    login(client)
    pid = seed["p1"].uid

    def png():
        b = io.BytesIO()
        Image.new("RGB", (40, 40), "red").save(b, "PNG")
        return b.getvalue()

    r1 = client.post(f"/api/v1/admin/products/{pid}/images", files={"file": ("a.png", png(), "image/png")}, headers=H)
    r2 = client.post(f"/api/v1/admin/products/{pid}/images", files={"file": ("b.png", png(), "image/png")}, headers=H)
    assert r1.json()["is_main"] is True and r2.json()["is_main"] is False
    assert client.post(f"/api/v1/admin/products/{pid}/images", files={"file": ("x.png", b"not an image", "image/png")}, headers=H).status_code == 415
    # removing the main image promotes the next one: product never points at a missing main image
    assert client.delete(f"/api/v1/admin/products/{pid}/images/{r1.json()['id']}", headers=H).status_code == 204
    imgs = client.get(f"/api/v1/admin/products/{pid}").json()["images"]
    assert len(imgs) == 1 and imgs[0]["is_main"] is True


def test_urls_use_uuids_not_sequential_numbers(client, seed):
    import re
    login(client)
    uuid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    p = client.get("/api/v1/admin/products").json()["items"][0]
    assert uuid_re.match(p["id"])
    assert client.get(f"/api/v1/admin/products/{p['id']}").status_code == 200
    assert client.get("/api/v1/admin/products/1").status_code == 422  # integers are no longer accepted
    assert uuid_re.match(client.get("/api/v1/products").json()["items"][0]["id"])  # public API too
    ref = client.post("/api/v1/quotes", json={"full_name": "Ada Obi", "customer_type": "retail", "phone": "08012345678",
                      "items": [{"product_id": seed["p1"].uid, "quantity": 1}]}).json()["reference"]
    q = client.get("/api/v1/admin/quotes", params={"q": ref}).json()["items"][0]
    assert uuid_re.match(q["id"])
    detail = client.get(f"/api/v1/admin/quotes/{q['id']}").json()
    assert detail["items"][0]["product_id"] == seed["p1"].uid  # links back to the catalogue by uuid
    assert client.post("/api/v1/quotes", json={"full_name": "Ada Obi", "customer_type": "retail", "phone": "08012345678",
                       "items": [{"product_id": 1, "quantity": 1}]}).status_code == 422
