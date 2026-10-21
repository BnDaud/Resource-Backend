from tests.conftest import H, login

FINISH = {"name": "Finish", "options": [{"label": "Matte"}, {"label": "Glossy", "color": "#FFFFFF"}]}
SIZE = {"name": "Size", "customer_picks": True, "options": [{"label": "8x4 ft"}, {"label": "7x3 ft"}]}
PICKED = {"name": "Pattern", "filterable": False, "customer_picks": False, "options": [{"label": "Synthetic"}]}
PROD = {"name": "Oak HDF Board", "sku": "FD-001", "availability": "available", "price_mode": "request"}


def save(client, scope, items):
    r = client.put(f"/api/v1/admin/attributes?scope={scope}", json=items, headers=H)
    assert r.status_code == 200, r.text
    return r.json()


def ids(attrs):
    return {a["name"]: {o["label"]: o["id"] for o in a["options"]} for a in attrs}


def setup(client, seed):
    login(client)
    division = ids(save(client, "section:boards", [FINISH, PICKED]))
    own = ids(save(client, f"category:{seed['cat'].id}", [SIZE]))
    return division, own


def test_division_attributes_are_inherited_by_its_categories(client, seed):
    division, own = setup(client, seed)
    names = lambda cid: [a["name"] for a in client.get(f"/api/v1/admin/categories/{cid}/attributes").json()]
    assert names(seed["cat"].id) == ["Finish", "Pattern", "Size"]  # the division's first, then the category's own
    assert names(seed["cat2"].id) == []  # an accessories category does not get the boards' attributes
    assert client.get(f"/api/v1/admin/attributes?scope=section:boards").json()[0]["options"][1]["color"] == "#ffffff"  # swatch colour is stored lowercase


def test_attribute_input_is_validated(client, seed):
    login(client)
    bad = lambda items, scope="section:boards": client.put(f"/api/v1/admin/attributes?scope={scope}", json=items, headers=H).status_code
    assert bad([{"name": "A", "options": [{"label": "x"}, {"label": "X"}]}]) == 422  # same option twice
    assert bad([{"name": "A", "options": [{"label": "x", "color": "red"}]}]) == 422  # colour must be #rrggbb
    assert bad([{"name": "A"}, {"name": "a"}]) == 422  # same attribute twice
    assert bad([FINISH], "section:doors") == 422
    assert bad([FINISH], "category:9999") == 404
    assert bad([{"id": 999, "name": "A"}]) == 422  # an id that is not in this scope
    assert client.put("/api/v1/admin/attributes?scope=section:boards", json=[FINISH]).status_code == 403  # needs the CSRF header


def test_product_options_are_checked_and_shown(client, seed):
    division, own = setup(client, seed)
    matte, size = division["Finish"]["Matte"], own["Size"]["8x4 ft"]
    r = client.put(f"/api/v1/admin/products/{seed['p1'].uid}", json={**PROD, "category_id": seed["cat"].id, "option_ids": [matte, size, matte]}, headers=H)
    assert r.status_code == 200, r.text
    assert sorted(r.json()["option_ids"]) == sorted([matte, size])
    shown = {a["name"]: [o["label"] for o in a["options"]] for a in client.get("/api/v1/products/oak-hdf-board").json()["attributes"]}
    assert shown == {"Finish": ["Matte"], "Size": ["8x4 ft"]}
    # an option of another category cannot be used
    other = ids(save(client, f"category:{seed['cat2'].id}", [{"name": "Width", "options": [{"label": "22 mm"}]}]))["Width"]["22 mm"]
    bad = client.put(f"/api/v1/admin/products/{seed['p1'].uid}", json={**PROD, "category_id": seed["cat"].id, "option_ids": [other]}, headers=H)
    assert bad.status_code == 422


def test_the_catalogue_filters_by_options(client, seed):
    division, own = setup(client, seed)
    matte, glossy, size = division["Finish"]["Matte"], division["Finish"]["Glossy"], own["Size"]["8x4 ft"]
    client.put(f"/api/v1/admin/products/{seed['p1'].uid}", json={**PROD, "category_id": seed["cat"].id, "option_ids": [matte, size]}, headers=H)
    skus = lambda *o: [p["sku"] for p in client.get("/api/v1/products", params={"opt": list(o)}).json()["items"]]
    assert skus(matte) == ["FD-001"]
    assert skus(glossy) == []
    assert skus(glossy, matte) == ["FD-001"]  # options of one attribute: any of them
    assert skus(matte, size) == ["FD-001"]
    assert skus(glossy, size) == []  # different attributes: all of them
    assert sorted(skus()) == ["ET-100", "FD-001"]


def test_public_filters_list_only_filterable_attributes(client, seed):
    setup(client, seed)
    names = lambda **q: [a["name"] for a in client.get("/api/v1/attributes", params=q).json()]
    assert names(category="hdf") == ["Finish", "Size"]  # Pattern is not a filter
    assert names(section="boards") == ["Finish"]
    assert names() == []
    assert client.get("/api/v1/attributes", params={"category": "nope"}).status_code == 404


def test_removing_options_and_attributes_takes_them_off_products(client, seed):
    division, own = setup(client, seed)
    matte, size = division["Finish"]["Matte"], own["Size"]["8x4 ft"]
    client.put(f"/api/v1/admin/products/{seed['p1'].uid}", json={**PROD, "category_id": seed["cat"].id, "option_ids": [matte, size]}, headers=H)
    current = client.get("/api/v1/admin/attributes?scope=section:boards").json()
    kept = [{"id": a["id"], "name": a["name"], "filterable": a["filterable"], "customer_picks": a["customer_picks"],
             "options": [{"id": o["id"], "label": o["label"], "color": o["color"]} for o in a["options"] if o["label"] != "Matte"]} for a in current]
    save(client, "section:boards", kept)
    assert client.get(f"/api/v1/admin/products/{seed['p1'].uid}").json()["option_ids"] == [size]
    save(client, f"category:{seed['cat'].id}", [])
    assert client.get(f"/api/v1/admin/products/{seed['p1'].uid}").json()["option_ids"] == []
