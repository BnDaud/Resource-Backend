import os

from cryptography.fernet import Fernet

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["FRONTEND_ORIGIN"] = "http://localhost:5173, https://project-uxn0h.vercel.app/"
# Throwaway keys made fresh for every test run, so no key-shaped string lives in the source.
os.environ["ENCRYPTION_KEYS"] = Fernet.generate_key().decode()
os.environ["BLIND_INDEX_KEY"] = "test-only-blind-index-key"
os.environ["SUPABASE_URL"] = "https://example.supabase.co"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "x"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.limiter import limiter
from app.core.security import hash_password
from app.main import app
from app.models import Category, Product, Role, Staff, Availability, PriceMode

H = {"X-Requested-With": "rc-cms"}


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as s:
        yield s
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    limiter.enabled = False
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def seed(db):
    cat = Category(name="Flush Doors", slug="flush-doors")
    cat2 = Category(name="Edges Tape", slug="edges-tape")
    db.add_all([cat, cat2])
    db.flush()
    ps = [
        Product(name="Oak Flush Door", slug="oak-flush-door", sku="FD-001", category_id=cat.id, brand="Acme",
                availability=Availability.available, price_mode=PriceMode.public, public_price=45000,
                wholesale_note="SECRET-WHOLESALE", stock_qty=77, is_featured=True),
        Product(name="White Edge Tape", slug="white-edge-tape", sku="ET-100", category_id=cat2.id,
                availability=Availability.out_of_stock),
        Product(name="Hidden Archived", slug="hidden", sku="AR-1", category_id=cat.id, is_archived=True),
    ]
    db.add_all(ps)
    db.add(Staff(email="admin@test.com", name="Admin", password_hash=hash_password("correct-horse-1"), role=Role.admin))
    db.add(Staff(email="ed@test.com", name="Ed", password_hash=hash_password("correct-horse-2"), role=Role.editor))
    db.commit()
    return {"cat": cat, "cat2": cat2, "p1": ps[0], "p2": ps[1], "archived": ps[2]}


def login(client, email="admin@test.com", pw="correct-horse-1"):
    r = client.post("/api/v1/admin/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r
