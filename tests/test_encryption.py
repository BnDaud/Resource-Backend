import pytest
from sqlalchemy import text

from app.core import crypto
from app.core.crypto import blind_index, decrypt, encrypt
from tests.conftest import login

PLAIN = ["Ada Obi", "08012345678", "ada@example.com", "SECRET-WHOLESALE", "admin@test.com", "Need 40 sheets urgently"]


def test_roundtrip_and_nonce():
    assert decrypt(encrypt("hello")) == "hello"
    assert encrypt("hello") != encrypt("hello")  # random IV: equal values do not look equal
    assert encrypt("hello") != "hello"


def test_wrong_key_cannot_read(monkeypatch):
    token = encrypt("secret")
    from cryptography.fernet import Fernet
    monkeypatch.setattr(crypto, "_fernet", lambda: __import__("cryptography.fernet", fromlist=["MultiFernet"]).MultiFernet([Fernet(Fernet.generate_key())]))
    with pytest.raises(ValueError):
        crypto.decrypt(token)


def test_key_rotation_keeps_old_data_readable(monkeypatch):
    from cryptography.fernet import Fernet, MultiFernet
    old, new = Fernet(Fernet.generate_key()), Fernet(Fernet.generate_key())
    token = old.encrypt(b"data").decode()
    monkeypatch.setattr(crypto, "_fernet", lambda: MultiFernet([new, old]))
    assert crypto.decrypt(token) == "data"


def test_database_holds_only_ciphertext(client, seed, db):
    client.post("/api/v1/quotes", json={"full_name": "Ada Obi", "customer_type": "retail", "phone": "08012345678",
                "email": "ada@example.com", "message": "Need 40 sheets urgently",
                "items": [{"product_id": seed["p1"].uid, "quantity": 1}]})
    client.post("/api/v1/enquiries", json={"name": "Ada Obi", "phone": "08012345678", "subject": "Hours", "message": "Open Sunday?"})
    login(client)
    pid = seed["p1"].uid
    # staff-only product fields
    stored = " ".join(
        str(v) for row in (
            db.execute(text("select full_name, phone, email, message, search_tokens from quote_requests")).all()
            + db.execute(text("select name, phone, subject, message from enquiries")).all()
            + db.execute(text("select email, name from staff")).all()
            + db.execute(text("select wholesale_note, stock_qty from products")).all()
        ) for v in row
    )
    for p in PLAIN + ["Hours", "Open Sunday?"]:
        assert p not in stored, f"plaintext leaked: {p}"
    # ...but the application reads everything back normally
    q = client.get("/api/v1/admin/quotes", params={"q": "RC-"}).json()["items"][0]
    detail = client.get(f"/api/v1/admin/quotes/{q['id']}").json()
    assert detail["full_name"] == "Ada Obi" and detail["email"] == "ada@example.com" and detail["message"].startswith("Need 40")
    prod = client.get(f"/api/v1/admin/products/{pid}").json()
    assert prod["wholesale_note"] == "SECRET-WHOLESALE" and prod["stock_qty"] == 77


def test_search_via_blind_index(client, seed):
    client.post("/api/v1/quotes", json={"full_name": "Chinedu Okafor", "customer_type": "retail", "phone": "+234 801 234 5678",
                "items": [{"product_id": seed["p1"].uid, "quantity": 1}]})
    login(client)
    s = lambda q: client.get("/api/v1/admin/quotes", params={"q": q}).json()["total"]
    assert s("chinedu") == 1 and s("OKAFOR") == 1
    assert s("08012345678") == 1 and s("+2348012345678") == 1  # local and international forms both match
    assert s("someone else") == 0
    assert s("chin") == 0  # whole words only: documented trade-off of encrypted search


def test_login_lookup_uses_blind_index(client, seed):
    assert client.post("/api/v1/admin/auth/login", json={"email": "ADMIN@test.com", "password": "correct-horse-1"}).status_code == 200
    assert blind_index("Admin@Test.com ") == blind_index("admin@test.com")
