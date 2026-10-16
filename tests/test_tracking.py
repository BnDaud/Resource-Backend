import re

from app.models import ProductImage, QuoteRequest
from tests.conftest import H, login

PHONE = "08031234567"


def quote(client, seed, phone=PHONE):
    return client.post("/api/v1/quotes", json={"full_name": "Chinedu Okafor", "customer_type": "retail", "phone": phone,
                       "items": [{"product_id": seed["p1"].uid, "quantity": 3, "note": "Oak, 2100x900"}]}).json()["reference"]


def test_enquiry_gets_a_reference(client, seed):
    r = client.post("/api/v1/enquiries", json={"name": "Funke A", "phone": PHONE, "subject": "Hours", "message": "Open Sunday?"})
    assert r.status_code == 201 and re.fullmatch(r"EN-\d{6}-[A-Z2-9]{4}", r.json()["reference"])


def test_track_quote_with_reference_and_phone(client, seed, db):
    ref = quote(client, seed)
    db.query(QuoteRequest).one().internal_notes = "SECRET staff note"
    db.commit()
    for phone in (PHONE, "+234 803 123 4567", "0803-123-4567"):  # any way of writing the same number
        r = client.post("/api/v1/track", json={"reference": ref.lower(), "phone": phone})
        assert r.status_code == 200, phone
    body = r.json()
    assert body["kind"] == "quote" and body["status"] == "new"
    assert body["items"] == [{"name": "Oak Flush Door", "sku": "FD-001", "quantity": 3, "note": "Oak, 2100x900"}]
    assert "SECRET" not in r.text and "Chinedu" not in r.text and PHONE not in r.text  # nothing private is returned


def test_track_shows_status_changes_made_in_the_cms(client, seed):
    ref = quote(client, seed)
    login(client)
    qid = client.get("/api/v1/admin/quotes", params={"q": ref}).json()["items"][0]["id"]
    client.patch(f"/api/v1/admin/quotes/{qid}", json={"status": "quoted"}, headers=H)
    assert client.post("/api/v1/track", json={"reference": ref, "phone": PHONE}).json()["status"] == "quoted"


def test_track_enquiry(client, seed):
    ref = client.post("/api/v1/enquiries", json={"name": "Funke A", "phone": PHONE, "subject": "Hours", "message": "Open Sunday?"}).json()["reference"]
    r = client.post("/api/v1/track", json={"reference": ref, "phone": PHONE}).json()
    assert r["kind"] == "enquiry" and r["subject"] == "Hours" and r["status"] == "new" and r["items"] == []


def test_wrong_phone_or_reference_look_identical(client, seed):
    ref = quote(client, seed)
    wrong_phone = client.post("/api/v1/track", json={"reference": ref, "phone": "08099999999"})
    unknown = client.post("/api/v1/track", json={"reference": "RC-000000-ZZZZ", "phone": PHONE})
    bad_prefix = client.post("/api/v1/track", json={"reference": "XX-000000-ZZZZ", "phone": PHONE})
    assert wrong_phone.status_code == unknown.status_code == bad_prefix.status_code == 404
    assert wrong_phone.json() == unknown.json() == bad_prefix.json()  # cannot tell which part was wrong


def test_category_cover_image_and_sitemap(client, seed, db):
    db.add(ProductImage(product_id=seed["p1"].id, url="https://cdn/x.webp", storage_path="x", is_main=True))
    db.commit()
    cats = {c["slug"]: c for c in client.get("/api/v1/categories").json()}
    assert cats["flush-doors"]["cover_image"] == "https://cdn/x.webp" and cats["edges-tape"]["cover_image"] is None
    xml = client.get("/sitemap.xml")
    assert xml.status_code == 200 and "application/xml" in xml.headers["content-type"]
    assert "/products/oak-flush-door" in xml.text and "/products/hidden" not in xml.text  # archived products are not listed
    assert "/admin" not in xml.text
