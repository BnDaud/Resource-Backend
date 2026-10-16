import re

from app.models import Product, QuoteItem, QuoteRequest
from tests.conftest import H, login

BASE = {"full_name": "Ada Obi", "customer_type": "wholesale", "phone": "08012345678"}


def payload(seed, **kw):
    return {**BASE, "items": [{"product_id": seed["p1"].uid, "quantity": 10}, {"product_id": seed["p2"].uid, "quantity": 3}], **kw}


def test_multi_item_quote_with_reference(client, seed, db):
    r = client.post("/api/v1/quotes", json=payload(seed))
    assert r.status_code == 201
    ref = r.json()["reference"]
    assert re.fullmatch(r"RC-\d{6}-[A-Z2-9]{4}", ref)
    q = db.query(QuoteRequest).one()
    assert q.reference == ref and len(q.items) == 2 and q.status.value == "new"
    assert {(i.product_sku, i.quantity) for i in q.items} == {("FD-001", 10), ("ET-100", 3)}


def test_duplicate_lines_are_merged(client, seed, db):
    p = {**BASE, "items": [{"product_id": seed["p1"].uid, "quantity": 2}, {"product_id": seed["p1"].uid, "quantity": 3}]}
    assert client.post("/api/v1/quotes", json=p).status_code == 201
    assert [i.quantity for i in db.query(QuoteItem)] == [5]


def test_rejects_bad_products_and_quantities(client, seed, db):
    assert client.post("/api/v1/quotes", json={**BASE, "items": [{"product_id": "00000000-0000-4000-8000-000000000000", "quantity": 1}]}).status_code == 422
    assert client.post("/api/v1/quotes", json={**BASE, "items": [{"product_id": seed["archived"].uid, "quantity": 1}]}).status_code == 422
    for qty in (0, -1, 100001):
        assert client.post("/api/v1/quotes", json={**BASE, "items": [{"product_id": seed["p1"].uid, "quantity": qty}]}).status_code == 422
    assert client.post("/api/v1/quotes", json={**BASE, "items": []}).status_code == 422
    assert db.query(QuoteRequest).count() == 0


def test_rejects_bad_customer_fields(client, seed):
    assert client.post("/api/v1/quotes", json=payload(seed, phone="x")).status_code == 422
    assert client.post("/api/v1/quotes", json=payload(seed, customer_type="vip")).status_code == 422
    assert client.post("/api/v1/quotes", json=payload(seed, email="bad")).status_code == 422
    assert client.post("/api/v1/quotes", json=payload(seed, preferred_contact="pigeon")).status_code == 422


def test_honeypot_stores_nothing(client, seed, db):
    assert client.post("/api/v1/quotes", json=payload(seed, website="spam")).status_code == 201
    assert db.query(QuoteRequest).count() == 0


def test_history_survives_rename_archive_and_delete(client, seed, db):
    ref = client.post("/api/v1/quotes", json=payload(seed)).json()["reference"]
    login(client)
    pid = seed["p1"].uid
    # rename via API, then archive
    body = {"name": "Renamed Door", "sku": "FD-001", "category_id": seed["cat"].id}
    assert client.put(f"/api/v1/admin/products/{pid}", json=body, headers=H).status_code == 200
    assert client.patch(f"/api/v1/admin/products/{pid}/archive", headers=H).status_code == 200
    q = db.query(QuoteRequest).filter_by(reference=ref).one()
    names = {i.product_name for i in q.items}
    assert "Oak Flush Door" in names  # snapshot unchanged
    # even a hard delete only nulls the link
    db.query(QuoteItem).count()
    db.delete(db.get(Product, seed["p1"].id))
    db.commit()
    db.expire_all()
    q = db.query(QuoteRequest).filter_by(reference=ref).one()
    assert len(q.items) == 2 and any(i.product_id is None and i.product_sku == "FD-001" for i in q.items)
