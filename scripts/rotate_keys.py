"""Re-encrypt every encrypted column with the newest key in ENCRYPTION_KEYS.

1. Generate a new key and put it FIRST in ENCRYPTION_KEYS (keep the old one after it, comma-separated).
2. Run:  python -m scripts.rotate_keys
3. Once it reports success, the old key can be removed.
"""
from sqlalchemy import text

from app.core.crypto import _fernet
from app.core.db import engine

COLUMNS = {
    "staff": ["email", "name"],
    "quote_requests": ["full_name", "phone", "email", "company", "message", "internal_notes"],
    "enquiries": ["name", "email", "phone", "subject", "message", "internal_notes"],
    "products": ["wholesale_note", "stock_qty"],
}
f = _fernet()
n = 0
with engine.begin() as conn:
    for table, cols in COLUMNS.items():
        for col in cols:
            for rid, val in conn.execute(text(f'SELECT id, "{col}" FROM {table} WHERE "{col}" IS NOT NULL AND "{col}" <> \'\'')).all():
                conn.execute(text(f'UPDATE {table} SET "{col}" = :v WHERE id = :i'), {"v": f.rotate(val.encode()).decode(), "i": rid})
                n += 1
print("re-encrypted", n, "values")
