"""Fill the CMS with clearly-labelled DEMO data so every screen has something to show.

    python -m scripts.demo_data            # add demo data (safe to re-run)
    python -m scripts.demo_data --remove   # delete every demo row and image, reset settings

Everything created here is marked so it can be removed cleanly:
  * products: SKU starts with "DEMO-"
  * quote requests: company "DEMO"
  * enquiries: subject starts with "[Demo]"
  * testimonials: name ends with "(demo)"
Names, prices, stock counts, contacts and testimonials are made up for demonstration only.
Photos are from Unsplash (free licence, no attribution required) in scripts/demo_assets/.
"""
import asyncio
import io
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import (
    Availability as A, Category, CustomerType, Enquiry, EnquiryStatus, PriceMode, Product, ProductImage,
    ProductSpec, QuoteItem, QuoteRequest, QuoteStatus, Testimonial,
)
from app.services import storage
from app.services.common import get_site_settings, new_reference, unique_slug

ASSETS = Path(__file__).parent / "demo_assets"
AV, OOS, REQ, DISC = A.available, A.out_of_stock, A.on_request, A.discontinued

# (category, name, sku, brand, short, description, sizes, colours, specs, availability, price, wholesale_note, stock, featured, new, images)
P = [
    ("Boards & Plywood", "18mm Marine Plywood Sheet", "BRD-001", "", "Moisture-resistant plywood for cabinets, doors and fittings.",
     "Multi-layer plywood with a smooth face, suited to kitchen carcasses, wardrobes and shop fittings. Cut-to-size requests available on enquiry.",
     ["8x4 ft", "7x3 ft"], ["Natural"], [("Thickness", "18 mm"), ("Core", "Hardwood"), ("Glue", "Water-resistant")], AV, 42500, "Bulk from 20 sheets: ask for rate", 120, True, False,
     ["boards__F6cL5B7Gnz8", "boards__NDQIHPA9Iv0"]),
    ("Boards & Plywood", "Melamine Faced Board, Oak Finish", "BRD-002", "", "Ready-to-use decorative board for furniture and wardrobes.",
     "Particle board faced with a durable oak-effect melamine surface. Pair with matching edge tape for a finished look.",
     ["8x4 ft"], ["Oak", "Walnut", "White", "Grey"], [("Thickness", "18 mm"), ("Surface", "Melamine"), ("Core", "Particle board")], AV, None, "Wholesale price per pallet on request", 64, False, True,
     ["boards__7m3ReTvWFKk", "boards__M_06s9uF0Ro"]),
    ("Flush Doors", "Walnut Veneer Flush Door", "FD-001", "", "Smooth flat-panel interior door with walnut veneer.",
     "A modern flush door with a clean, handle-ready face. Supplied unglazed and without hinges or lock.",
     ["2100 x 900 mm", "2100 x 800 mm", "2100 x 700 mm"], ["Walnut"], [("Style", "Flush"), ("Thickness", "40 mm"), ("Use", "Interior")], AV, 68000, "Trade discount on 10+ doors", 38, True, False,
     ["flush-doors__B9KcyJ7K-DY"]),
    ("Flush Doors", "White Painted Flush Door", "FD-002", "", "Primed white flush door, ready to fit.",
     "Lightweight hollow-core door with a smooth white finish. Suitable for bedrooms, offices and closets.",
     ["2100 x 900 mm", "2100 x 800 mm"], ["White"], [("Style", "Flush"), ("Core", "Hollow"), ("Finish", "Painted")], REQ, None, "", None, False, False,
     ["flush-doors__hMsHf0gdMow", "flush-doors__3PWBgE7IpaI"]),
    ("Door Boards", "Mahogany Door Skin Board", "DB-001", "", "Veneered board for facing and repairing doors.",
     "Thin decorative board in a rich mahogany tone for door facing, panelling and cabinet doors.",
     ["2440 x 1220 mm"], ["Mahogany"], [("Thickness", "4 mm"), ("Face", "Mahogany veneer")], AV, None, "Carton of 10: ask for rate", 90, False, False,
     ["door-boards__RiwLW247fpU"]),
    ("Door Boards", "Light Oak Veneer Door Board", "DB-002", "", "Light oak surface for modern door and panel work.",
     "Pale oak-look board with natural grain variation, suitable for doors, wall panels and furniture faces.",
     ["2440 x 1220 mm"], ["Light oak"], [("Thickness", "6 mm"), ("Face", "Oak veneer")], OOS, None, "Next delivery expected: ask", 0, False, True,
     ["door-boards__JH_R66BihvA"]),
    ("Edges Tape", "Wood Veneer Edge Banding Roll", "ET-001", "", "Iron-on veneer tape for finishing board edges.",
     "Real-wood-look edge banding with pre-applied adhesive. Matches common oak and walnut boards.",
     ["22 mm x 50 m", "22 mm x 25 m"], ["Oak", "Walnut", "Maple"], [("Material", "Wood veneer"), ("Adhesive", "Pre-glued"), ("Width", "22 mm")], AV, 9500, "Box of 10 rolls: ask for rate", 210, True, False,
     ["edge-tape__H7p4qn4G79I"]),
    ("Edges Tape", "PVC Edge Tape, Clear", "ET-002", "", "Flexible PVC tape for curved and straight edges.",
     "Durable PVC edge tape that resists knocks and moisture. Applied with a household iron or an edge bander.",
     ["22 mm x 50 m"], ["Clear", "White", "Yellow"], [("Material", "PVC"), ("Thickness", "1 mm")], AV, None, "", 150, False, False,
     ["edge-tape__8pYVLSL9c5Q", "edge-tape__uYGlkouvs0c"]),
    ("Profiles", "Aluminium Heat-Sink Profile", "PR-001", "", "Extruded aluminium profile with cooling fins.",
     "Brushed aluminium profile with fins, used for LED strip lighting and electronics housings in cabinetry.",
     ["1 m", "2 m", "3 m"], ["Silver", "Black"], [("Material", "Aluminium"), ("Finish", "Brushed anodised")], AV, 12500, "Cut lengths available", 75, False, False,
     ["profiles__bkL2Z-76v8Y"]),
    ("Profiles", "Assorted Aluminium Channel Profiles", "PR-002", "", "Angles, tubes and channels for framing and trim.",
     "A range of square, round and angle sections for shelving frames, edge trims and light fabrication.",
     ["1 m", "2 m", "3 m"], ["Silver"], [("Material", "Aluminium"), ("Shapes", "Angle, tube, channel")], REQ, None, "", None, False, True,
     ["profiles__UObdhwSso5o", "profiles__pQyJRYkxGX4"]),
    ("Glass Profiles", "Black Aluminium Glass Door Frame Profile", "GP-001", "", "Slim black frame for glass doors and partitions.",
     "Thin-line black aluminium profile for framed glass doors, room dividers and display units.",
     ["3 m"], ["Matt black"], [("Material", "Aluminium"), ("Glass", "Up to 8 mm")], AV, 38500, "", 40, True, False,
     ["glass-profiles__Ax6IJkNFXX4", "glass-profiles__ifaw-WZL7-Y"]),
    ("Glass Profiles", "Slim Glass Partition Profile", "GP-002", "", "Profile set for glazed office and home partitions.",
     "Lightweight framing system for partitions with clear or frosted glass panels.",
     ["3 m"], ["Matt black", "Silver"], [("Material", "Aluminium"), ("Use", "Partitions, sliding doors")], REQ, None, "Project pricing on request", None, False, False,
     ["glass-profiles__yWwob8kwOCk", "glass-profiles__ysgELOy_t0c"]),
    ("Kitchen Accessories", "Soft-Close Drawer Organiser Set", "KA-001", "", "Divider set that keeps plates, bowls and spices tidy.",
     "Modular organiser inserts for deep kitchen drawers. Adjustable dividers fit common cabinet widths.",
     ["600 mm", "800 mm", "900 mm"], ["Grey"], [("Fits", "Standard drawers"), ("Material", "Plastic and steel")], AV, 24500, "", 55, True, True,
     ["kitchen-acc__BngKr53ZvR4"]),
    ("Kitchen Accessories", "Matt Black Cabinet Handle", "KA-002", "", "Bold bar handle for doors and drawers.",
     "Solid bar handle with a textured grip in matt black. Supplied with screws.",
     ["128 mm", "160 mm", "224 mm"], ["Matt black", "Brushed steel"], [("Material", "Zinc alloy"), ("Finish", "Matt")], AV, 3500, "Box of 50: ask for rate", 300, False, False,
     ["kitchen-acc__a8OuPQdyvIs", "kitchen-acc__uRBHzqrUHDY"]),
    ("Oven & Burners", "4-Burner Built-in Gas Hob", "OB-001", "", "Black glass-top gas hob with cast pan supports.",
     "Four-burner hob for worktop installation with heavy cast supports and front control knobs.",
     ["60 cm", "75 cm"], ["Black"], [("Burners", "4"), ("Fuel", "Gas"), ("Install", "Built-in")], AV, 185000, "Dealer price on request", 12, True, False,
     ["oven-burners__1bQSP0_iLMc", "oven-burners__1LF-R7AGQfo"]),
    ("Oven & Burners", "Freestanding Gas Range Cooker", "OB-002", "", "Oven and hob in one for family kitchens.",
     "Stainless-steel range cooker with gas hob and oven. Delivery and installation available.",
     ["60 cm", "90 cm"], ["Stainless steel", "White"], [("Fuel", "Gas"), ("Oven", "Yes")], REQ, None, "", None, False, True,
     ["oven-burners__7e89a3H2x7A", "oven-burners__gRQ2hAP7e_A", "oven-burners__GtX2B8e84z4"]),
    ("Heat Extractors", "Slimline Wall-Mounted Extractor Hood", "HE-001", "", "Stainless-steel hood that clears cooking fumes.",
     "Wall-mounted extractor with a slim canopy and quiet motor. Ducted or recirculating.",
     ["60 cm", "90 cm"], ["Stainless steel"], [("Type", "Wall-mounted"), ("Speeds", "3")], AV, 96000, "", 18, False, False,
     ["extractors__U9liWDW4xA0"]),
    ("Heat Extractors", "Concealed Under-Cabinet Extractor Hood", "HE-002", "", "Discreet hood that blends into your cabinets.",
     "Built-in hood designed to sit inside wall units or panelling for a clean, minimal look.",
     ["60 cm", "90 cm"], ["Black", "White"], [("Type", "Built-in"), ("Finish", "Painted steel")], DISC, None, "Clearance stock only", 3, False, False,
     ["extractors__VcavCyYVae0", "extractors__oKQoNdMoB8o"]),
    ("Plate Racks", "Chrome Plate Drying Rack", "PL-001", "", "Wire rack that keeps plates upright to dry.",
     "Easy-clean chrome rack with a drip tray, for worktops or inside cabinets.",
     ["Standard"], ["Chrome"], [("Material", "Chrome-plated steel"), ("Capacity", "12 plates")], AV, 7500, "", 140, False, False,
     ["plate-racks__JevtSj7GbEo", "plate-racks__tfIxn4GW6yU"]),
    ("Plate Racks", "Countertop Dish Drainer Basket", "PL-002", "", "Compact drainer for cups, plates and cutlery.",
     "Compact drainer with a cutlery caddy. Sits neatly beside the sink.",
     ["Compact"], ["White", "Grey"], [("Material", "Plastic and steel")], AV, None, "", 85, False, False,
     ["plate-racks__eAo06YJ0N5U", "plate-racks__a8Uh-i1tZbg"]),
    ("Pull-Out Hanger Profiles", "Pull-Out Wardrobe Hanging Rail", "PH-001", "", "Sliding rail that brings clothes to you.",
     "Side-mount pull-out rail for wardrobes, giving full access to hanging space.",
     ["450 mm", "550 mm", "650 mm"], ["Chrome", "Black"], [("Load", "Up to 15 kg"), ("Mount", "Side")], AV, 15500, "", 70, True, False,
     ["hanger__qlAWpiUiFyc", "hanger__9KVtDmNnFP4"]),
    ("Pull-Out Hanger Profiles", "Telescopic Wardrobe Rail", "PH-002", "", "Adjustable rail that fits different wardrobe widths.",
     "Extendable rail with end sockets for fitted and freestanding wardrobes.",
     ["600-1000 mm", "1000-1500 mm"], ["Chrome", "White"], [("Material", "Steel"), ("Adjustable", "Yes")], REQ, None, "", None, False, True,
     ["hanger__Yy4sN6QzboU", "hanger__SseNV6Ycb1c"]),
    ("Wine Racks", "Wall-Mounted Wine Rack", "WR-001", "", "Showcases bottles on the wall.",
     "Wall-fixed rack that holds bottles horizontally. Pairs well with back-lighting.",
     ["12 bottles", "24 bottles"], ["Black", "Silver"], [("Capacity", "12 or 24 bottles"), ("Mount", "Wall")], AV, 45000, "", 22, False, True,
     ["wine-racks__FgRS7KHMSV0", "wine-racks__ESe8lx0r3oM"]),
    ("Wine Racks", "Wooden Wine Display Rack", "WR-002", "", "Solid wood rack for cellars and bars.",
     "Timber rack with angled slots to keep bottles stable and labels visible.",
     ["18 bottles", "36 bottles"], ["Dark oak"], [("Material", "Solid wood")], OOS, 68000, "Restocking soon", 0, False, False,
     ["wine-racks__cyYDM3OLMG8", "wine-racks__up2MCIqvpMg"]),
    ("Magic Corners", "Magic Corner Pull-Out Unit", "MC-001", "", "Brings blind corner storage into reach.",
     "Two-tier swing-out basket system that makes use of awkward corner cabinets.",
     ["500 mm", "600 mm"], ["Grey"], [("Cabinet", "Corner"), ("Baskets", "2")], AV, 112000, "", 9, True, False,
     ["magic-corner__1voJQ66DIDM", "magic-corner__K5JI_wRQqY0"]),
    ("Magic Corners", "Blind Corner Swing-Out Unit", "MC-002", "", "Full access to deep corner cabinets.",
     "Swing-out shelving for blind-corner base units with soft-close action.",
     ["450 mm", "500 mm"], ["Grey", "White"], [("Cabinet", "Blind corner")], REQ, None, "", None, False, False,
     ["magic-corner__DQpUeNzRj6s", "magic-corner__oXOCQ4V1RxY"]),
    ("Spoon Racks", "Hanging Utensil Rail with Hooks", "SR-001", "", "Wall rail that keeps utensils in easy reach.",
     "Stainless steel rail with sliding hooks for ladles, spoons and whisks.",
     ["60 cm", "90 cm"], ["Stainless steel", "Black"], [("Material", "Stainless steel"), ("Hooks", "10")], AV, 8500, "", 95, False, False,
     ["spoon-racks__zYMyL_QSSE8", "spoon-racks__BYm1kkFasEI"]),
    ("Spoon Racks", "Countertop Spoon and Utensil Holder", "SR-002", "", "Ceramic holder for everyday spoons and spatulas.",
     "Weighted holder that stays put on the worktop.",
     ["Small", "Large"], ["White", "Terracotta"], [("Material", "Ceramic")], AV, None, "", 60, False, True,
     ["spoon-racks__-4dlgog2T_4", "spoon-racks__68CDDj03rks"]),
    ("Microwave", "Built-in Microwave Oven, 25 L", "MW-001", "", "Black built-in microwave for tall units.",
     "Integrated microwave with digital controls, designed for cabinet installation.",
     ["25 L"], ["Black"], [("Capacity", "25 L"), ("Install", "Built-in")], AV, 132000, "", 14, True, False,
     ["microwave__OZPVdo-YQjE"]),
    ("Microwave", "Countertop Microwave Oven, 20 L", "MW-002", "", "Compact microwave for any worktop.",
     "Simple dial or digital microwave for small kitchens and offices.",
     ["20 L"], ["White", "Silver"], [("Capacity", "20 L"), ("Install", "Countertop")], AV, 58000, "", 31, False, False,
     ["microwave__WtxE9xb0vQU", "microwave__1eWGq_l_DuU"]),
    ("Other Products", "Brass Door Lever Handle", "OT-001", "", "Classic brass lever for interior doors.",
     "Solid lever handle with a warm brass finish. Sold as a set with rose plates.",
     ["Standard"], ["Brass"], [("Material", "Brass"), ("Use", "Interior doors")], AV, 11500, "", 80, False, False,
     ["other__hfiainyla0c", "other__qZN0ChmJdhg"]),
    ("Other Products", "Satin Steel Door Lever Handle", "OT-002", "", "Modern lever in a satin steel finish.",
     "Contemporary lever handle that suits flush doors and glass doors.",
     ["Standard"], ["Satin steel", "Black"], [("Material", "Stainless steel")], AV, 9800, "", 110, False, True,
     ["other__aTyWIycz73A", "other__UxxbbqErPRY"]),
]

TESTIMONIALS = [
    ("Chinedu O. (demo)", "Contractor", "Quick response on our quote and the doors arrived exactly as described. Easy to deal with.", True),
    ("Ngozi A. (demo)", "Homeowner", "Found everything for my kitchen in one place and the team helped me choose the right handles.", True),
    ("Tunde B. (demo)", "Furniture workshop", "Good range of boards and edge tape. Reliable for repeat orders.", True),
    ("Amaka E. (demo)", "Interior designer", "Draft testimonial awaiting approval.", False),
]

QUOTES = [  # name, type, phone, email, message, status, notes, [(sku, qty)], days ago
    ("Chinedu Okafor", CustomerType.wholesale, "08031234567", "chinedu@example.com", "Need 20 doors and matching edge tape for a site in Ikeja.", QuoteStatus.new, "", [("DEMO-FD-001", 20), ("DEMO-ET-001", 15)], 0),
    ("Ngozi Adebayo", CustomerType.retail, "08059876543", "", "Looking for handles and a drawer organiser for a new kitchen.", QuoteStatus.under_review, "Called back, waiting for measurements.", [("DEMO-KA-002", 18), ("DEMO-KA-001", 2)], 1),
    ("Tunde Bello", CustomerType.wholesale, "07011223344", "tunde@example.com", "Regular order: boards, tape and profiles for the workshop.", QuoteStatus.quoted, "Quote sent on WhatsApp. Follow up Friday.", [("DEMO-BRD-001", 40), ("DEMO-BRD-002", 30), ("DEMO-ET-002", 10)], 3),
    ("Amaka Eze", CustomerType.retail, "09077665544", "amaka@example.com", "Hob and extractor hood for a small apartment kitchen.", QuoteStatus.accepted, "Deposit received.", [("DEMO-OB-001", 1), ("DEMO-HE-001", 1)], 6),
    ("Ibrahim Musa", CustomerType.wholesale, "08122334455", "", "Glass profiles for an office fit-out.", QuoteStatus.closed, "Customer went with another supplier.", [("DEMO-GP-001", 12)], 14),
]

ENQUIRIES = [
    ("Funke Adeyemi", "08066778899", "funke@example.com", "[Demo] Opening hours", "Are you open on Saturdays? I'd like to visit your shop.", EnquiryStatus.new, ""),
    ("Samuel Okoro", "08133445566", "", "[Demo] Delivery to Abuja", "Do you deliver outside Lagos and how long does it take?", EnquiryStatus.read, ""),
    ("Grace Nwosu", "07033221100", "grace@example.com", "[Demo] Wholesale terms", "What are the minimum quantities for wholesale prices on edge tape?", EnquiryStatus.replied, "Replied by phone, sent price list."),
    ("Kola Fashola", "08099887766", "", "[Demo] Custom cut boards", "Can you cut plywood to size for me?", EnquiryStatus.archived, "Handled in store."),
]

DEMO_SETTINGS = dict(
    business_name="Resources Components", opening_hours="Mon-Sat, 8am - 6pm (demo)",
    phone="+234 800 000 0000", email="hello@example.com", whatsapp_number="2348000000000",
    instagram_url="https://instagram.com/", tiktok_url="https://tiktok.com/",
    seo_title="Resources Components | Kitchen, furniture and building components",
    seo_description="Wholesale and retail kitchen, furniture and building components in Mushin, Lagos. Browse products and request a quote.",
)


async def _opt(stem: str) -> bytes:
    class F:  # minimal UploadFile stand-in for read_and_optimise
        def __init__(self, data): self._d = io.BytesIO(data)
        async def read(self, n=-1): return self._d.read(n)
    return await storage.read_and_optimise(F((ASSETS / f"{stem}.jpg").read_bytes()))  # type: ignore[arg-type]


def demo_quotes(db) -> list:
    """Company and subject are encrypted in the database, so they cannot be matched in SQL: filter after decrypting."""
    return [q for q in db.scalars(select(QuoteRequest)) if q.company == "DEMO"]


def demo_enquiries(db) -> list:
    return [e for e in db.scalars(select(Enquiry)) if e.subject.startswith("[Demo]")]


async def add() -> None:
    with SessionLocal() as db:
        cats = {c.name: c for c in db.scalars(select(Category))}
        have = set(db.scalars(select(Product.sku).where(Product.sku.like("DEMO-%"))))
        made = 0
        for (cat, name, sku, brand, short, desc, sizes, colours, specs, avail, price, wnote, stock, feat, new, imgs) in P:
            sku = f"DEMO-{sku}"
            if sku in have:
                continue
            p = Product(
                name=name, sku=sku, category_id=cats[cat].id, brand=brand, short_description=short, description=desc,
                sizes=sizes, colours=colours, availability=avail,
                price_mode=PriceMode.public if price else PriceMode.request, public_price=Decimal(price) if price else None,
                wholesale_note=wnote, stock_qty=stock, is_featured=feat, is_new=new,
                specs=[ProductSpec(name=n, value=v, sort_order=i) for i, (n, v) in enumerate(specs)],
            )
            p.slug = unique_slug(db, Product, name)
            db.add(p)
            db.flush()
            for i, stem in enumerate(imgs):
                path, url = await storage.upload(f"products/{p.id}", await _opt(stem))
                db.add(ProductImage(product_id=p.id, url=url, storage_path=path, alt=name, is_main=i == 0, sort_order=i))
            db.commit()
            made += 1
            print("product", sku)

        skus = {p.sku: p for p in db.scalars(select(Product).where(Product.sku.like("DEMO-%")))}
        if not demo_quotes(db):
            for (n, t, ph, em, msg, st, notes, items, days) in QUOTES:
                when = datetime.now(timezone.utc) - timedelta(days=days, hours=days)
                q = QuoteRequest(
                    reference=new_reference(when), full_name=n, customer_type=t, phone=ph, email=em, company="DEMO",
                    message=msg, preferred_contact="whatsapp", status=st, internal_notes=notes, created_at=when,
                    items=[QuoteItem(product_id=skus[s].id, product_name=skus[s].name, product_sku=s, quantity=q_) for s, q_ in items],
                )
                db.add(q)
            db.commit()
            print("quotes", len(QUOTES))
        if not demo_enquiries(db):
            for i, (n, ph, em, sub, msg, st, notes) in enumerate(ENQUIRIES):
                db.add(Enquiry(name=n, phone=ph, email=em, subject=sub, message=msg, status=st, internal_notes=notes,
                               created_at=datetime.now(timezone.utc) - timedelta(days=i * 2)))
            db.commit()
            print("enquiries", len(ENQUIRIES))
        if not db.scalar(select(Testimonial.id).where(Testimonial.display_name.like("%(demo)"))):
            for n, c, t, pub in TESTIMONIALS:
                db.add(Testimonial(display_name=n, company=c, text=t, is_published=pub))
            db.commit()
            print("testimonials", len(TESTIMONIALS))
        s = get_site_settings(db)
        for k, v in DEMO_SETTINGS.items():
            setattr(s, k, v)
        db.commit()
        print("settings filled; new products:", made)


async def remove() -> None:
    with SessionLocal() as db:
        for q in demo_quotes(db):
            db.delete(q)
        for e in demo_enquiries(db):
            db.delete(e)
        for t in db.scalars(select(Testimonial).where(Testimonial.display_name.like("%(demo)"))):
            db.delete(t)
        for p in db.scalars(select(Product).where(Product.sku.like("DEMO-%"))):
            for img in p.images:
                await storage.delete(img.storage_path)
            db.delete(p)
        s = get_site_settings(db)
        s.business_name = s.seo_title = "Resources Components"
        s.opening_hours = s.phone = s.email = s.whatsapp_number = s.instagram_url = s.tiktok_url = s.seo_description = ""
        db.commit()
        print("demo data removed")


if __name__ == "__main__":
    asyncio.run(remove() if "--remove" in sys.argv else add())
