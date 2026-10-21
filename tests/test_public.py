

def test_categories_and_counts(client, seed):
    r = client.get("/api/v1/categories")
    assert r.status_code == 200
    d = {c["name"]: c["product_count"] for c in r.json()}
    assert d == {"HDF": 1, "Edges Tape": 1}  # archived product not counted


def test_categories_carry_their_section_and_products_filter_by_it(client, seed):
    sections = {c["name"]: c["section"] for c in client.get("/api/v1/categories").json()}
    assert sections == {"HDF": "boards", "Edges Tape": "accessories"}
    names = lambda **q: [p["name"] for p in client.get("/api/v1/products", params=q).json()["items"]]
    assert names(section="boards") == ["Oak HDF Board"]
    assert names(section="accessories") == ["White Edge Tape"]
    assert names(section="boards", category="edges-tape") == []  # a category of the other division matches nothing
    assert client.get("/api/v1/products", params={"section": "doors"}).status_code == 422


def test_product_list_hides_private_and_archived(client, seed):
    r = client.get("/api/v1/products")
    body = r.json()
    assert body["total"] == 2
    assert "SECRET-WHOLESALE" not in r.text and "wholesale_note" not in r.text and "stock_qty" not in r.text
    assert all(p["slug"] != "hidden" for p in body["items"])


def test_price_only_when_public(client, seed):
    items = {p["sku"]: p for p in client.get("/api/v1/products").json()["items"]}
    assert float(items["FD-001"]["public_price"]) == 45000
    assert items["ET-100"]["public_price"] is None and items["ET-100"]["price_mode"] == "request"


def test_search_by_name_sku_and_brand(client, seed):
    f = lambda q: [p["sku"] for p in client.get("/api/v1/products", params={"q": q}).json()["items"]]
    assert f("oak") == ["FD-001"]
    assert f("et-100") == ["ET-100"]
    assert f("acme") == ["FD-001"]
    assert f("zzzz") == []
    assert f("100%") == []  # % is literal, not a wildcard


def test_filters_sort_and_pagination(client, seed):
    g = lambda **p: client.get("/api/v1/products", params=p).json()
    assert [x["sku"] for x in g(category="edges-tape")["items"]] == ["ET-100"]
    assert [x["sku"] for x in g(availability="out_of_stock")["items"]] == ["ET-100"]
    assert [x["sku"] for x in g(featured="true")["items"]] == ["FD-001"]
    assert [x["name"] for x in g(sort="alpha")["items"]] == ["Oak HDF Board", "White Edge Tape"]
    page = g(page_size=1, page=2)
    assert page["pages"] == 2 and len(page["items"]) == 1
    assert client.get("/api/v1/products", params={"sort": "bogus"}).status_code == 422


def test_detail_availability_related(client, seed):
    d = client.get("/api/v1/products/oak-hdf-board").json()
    assert d["category_slug"] == "hdf" and "wholesale_note" not in d
    assert client.get("/api/v1/products/hidden").status_code == 404
    assert client.get("/api/v1/products/oak-hdf-board/related").status_code == 200


def test_enquiry_validation_and_honeypot(client, seed, db):
    from app.models import Enquiry
    ok = {"name": "Ada", "phone": "+234 801 234 5678", "subject": "Hours", "message": "When are you open?"}
    assert client.post("/api/v1/enquiries", json=ok).status_code == 201
    assert db.query(Enquiry).count() == 1
    assert client.post("/api/v1/enquiries", json={**ok, "phone": "abc"}).status_code == 422
    assert client.post("/api/v1/enquiries", json={**ok, "email": "nope"}).status_code == 422
    client.post("/api/v1/enquiries", json={**ok, "website": "http://spam"})
    assert db.query(Enquiry).count() == 1  # honeypot stored nothing


def test_only_published_testimonials_and_settings(client, seed, db):
    from app.models import Testimonial
    db.add_all([Testimonial(display_name="A", text="Great service", is_published=True),
                Testimonial(display_name="B", text="Draft one", is_published=False)])
    db.commit()
    r = client.get("/api/v1/testimonials").json()
    assert [t["display_name"] for t in r] == ["A"]
    s = client.get("/api/v1/settings").json()
    assert s["business_name"] == "Resources Components" and "Mushin" in s["address"]
