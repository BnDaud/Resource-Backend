"""Application-level encryption for personal and private business data.

* Values are encrypted with Fernet (AES-128-CBC + HMAC-SHA256) before they reach the database,
  so a database dump, backup or a look through the Supabase dashboard shows only ciphertext.
* ENCRYPTION_KEYS holds one or more keys, newest first. New data uses the first key; old rows
  stay readable with older keys, so keys can be rotated (see scripts/rotate_keys.py).
* Encrypted columns cannot be searched in SQL, so searchable fields also store a *blind index*:
  an HMAC of the normalised value under a separate key. It supports exact lookups only.
"""
import hashlib
import hmac
import re
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.core.config import get_settings


@lru_cache
def _fernet() -> MultiFernet:
    keys = [k.strip() for k in get_settings().encryption_keys.split(",") if k.strip()]
    if not keys:
        raise RuntimeError("ENCRYPTION_KEYS is empty")
    return MultiFernet([Fernet(k.encode()) for k in keys])


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Cannot decrypt value: wrong or missing ENCRYPTION_KEYS") from exc


def blind_index(value: str) -> str:
    key = get_settings().blind_index_key.encode()
    return hmac.new(key, value.strip().lower().encode(), hashlib.sha256).hexdigest()[:32]


class EncryptedText(TypeDecorator):
    """Stores text as Fernet ciphertext. Empty string and NULL pass through unchanged."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt(value) if value else value

    def process_result_value(self, value, dialect):
        return decrypt(value) if value else value


class EncryptedInt(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else encrypt(str(int(value)))

    def process_result_value(self, value, dialect):
        return None if not value else int(decrypt(value))


def search_tokens(*texts: str, phone: str = "") -> str:
    """Space-separated blind indexes for each word of the texts and each form of a phone number."""
    out: set[str] = set()
    for t in texts:
        for w in re.findall(r"[a-z0-9]{2,}", (t or "").lower()):
            out.add(blind_index(w))
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) >= 7:
        out.add(blind_index(digits))
        out.add(blind_index(digits[-10:]))  # 0801… and +234801… both match
    return " ".join(sorted(out))


def query_tokens(q: str) -> list[str]:
    """Hashes to look for when an admin searches. Words, plus phone forms when it looks like a number."""
    q = q.strip()
    digits = re.sub(r"\D", "", q)
    toks = {blind_index(w) for w in re.findall(r"[a-z0-9]{2,}", q.lower())}
    if len(digits) >= 7:
        toks |= {blind_index(digits), blind_index(digits[-10:])}
    return sorted(toks)


def phone_tokens(phone: str) -> list[str]:
    """Blind indexes for the ways one phone number can be written (0801… and +234801…)."""
    digits = re.sub(r"\D", "", phone or "")
    return [blind_index(digits), blind_index(digits[-10:])] if len(digits) >= 7 else []
