# Resources Components: backend

FastAPI + SQLAlchemy API on Supabase Postgres and Storage. It serves the customer website and the staff CMS (both in the frontend repo).

- **Staff login:** email + password in our own `staff` table (bcrypt), httpOnly SameSite=Lax cookie, CSRF header on every state-changing admin request, roles `admin` / `editor`, rate-limited login.
- **Two divisions.** Every category belongs to a division, **Boards** (HDF, MDF, Blockboard) or **Accessories** (everything else), set in the CMS. `GET /api/v1/products?section=boards|accessories` filters by division.
- **Filters and options.** A division or a category offers choices such as Finish, Colour (with swatches) or Size. Staff define them in the CMS (Categories, "Filters and options"), tick the ones each product has, and customers filter by them and pick between them when they ask for a quote (`GET /api/v1/attributes`, `GET /api/v1/products?opt=<option id>`). The choices travel with the quote line as text. Colours can carry a catalogue code and a photo, and the boards ship with the standard RAL Classic range (217 colours, `scripts/ral_classic.json`) as "Special colour"; customers pick from a searchable swatch grid. RAL values are the usual on-screen approximations; the printed colour sheet is the reference.
- **Public ids are UUIDs** (products, quote requests, enquiries). Integer keys stay internal.
- **Encrypted at rest:** staff names/emails, customer names, phones, emails, messages, internal notes, and staff-only product fields are encrypted (Fernet) before they reach the database. Searching uses blind indexes (whole words / full phone numbers).
- **Customers have no accounts.** Quotes and enquiries get references (`RC-…`, `EN-…`); `POST /api/v1/track` needs reference **and** phone and returns status only.
- Row Level Security is enabled on every table, so Supabase's own REST API (anon key) cannot read or write anything.

```
app/
  core/       config, database, security, encryption, rate limiter
  models.py   tables
  schemas/    request/response models, one file per domain
  routers/    one file per resource (public, admin_products, admin_quotes, seo, ...)
  services/   business rules (quote creation, image storage, slugs)
alembic/      migrations
scripts/      seed, create_admin, setup_storage, demo_data, rotate_keys
tests/
```

## Setup

Python 3.12 (pinned in `.python-version`; newer Python versions such as 3.14 are not supported by the pinned SQLAlchemy yet).

1. **Supabase:** create a project. Copy the **Session pooler** connection string (the direct host is IPv6-only), the project URL and the **service_role** key.
2. ```bash
   python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt   # requirements.txt alone is what production needs
   cp .env.example .env                       # fill it in
   .venv/bin/alembic upgrade head             # create tables
   .venv/bin/python -m scripts.seed           # 17 starter categories, their filters and options + settings row
   .venv/bin/python -m scripts.setup_storage  # public-read image bucket
   .venv/bin/python -m scripts.create_admin you@example.com "Your Name"   # prompts for a password
   .venv/bin/uvicorn app.main:app --reload --port 8000
   ```
   API docs (development only): http://localhost:8000/docs

| Variable | Meaning |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://postgres.<ref>:<url-encoded password>@aws-0-<region>.pooler.supabase.com:5432/postgres` |
| `SUPABASE_URL` | `https://<ref>.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | secret key, server only |
| `SUPABASE_BUCKET` | `product-images` |
| `JWT_SECRET` | long random string (signs session cookies) |
| `ENCRYPTION_KEYS` | Fernet key(s), newest first: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `BLIND_INDEX_KEY` | long random string for searchable lookups. Never change it casually |
| `FRONTEND_ORIGIN` | website origin(s) allowed by CORS, comma-separated, no trailing slash, e.g. `http://localhost:5173,https://project-uxn0h.vercel.app` |
| `SITE_URL` | public website address (sitemap) |
| `COOKIE_SECURE` | `true` in production (HTTPS) |
| `ENVIRONMENT` | `production` hides `/docs` |

**Back up `ENCRYPTION_KEYS` and `BLIND_INDEX_KEY` separately from the database. Lose them and the encrypted data is unrecoverable.** To rotate: put a new key first in `ENCRYPTION_KEYS`, run `python -m scripts.rotate_keys`, then remove the old key.

## Demo data

`python -m scripts.demo_data` fills the CMS with clearly labelled demo products (with photos), quotes, enquiries, testimonials and settings. `python -m scripts.demo_data --remove` deletes all of it. The prices, phone, email and WhatsApp number it sets are made up; replace them before showing real customers.

## Tests

```bash
.venv/bin/python -m pytest
```

## Deployment

Host in the **same region as the Supabase database** (every cross-continent round trip costs ~170 ms). Run `alembic upgrade head` on deploy, `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers`, serve over HTTPS, set `COOKIE_SECURE=true` and `ENVIRONMENT=production`. Rate limits: quotes/enquiries 10/hour, tracking 20/hour, login 8/minute (per IP).
