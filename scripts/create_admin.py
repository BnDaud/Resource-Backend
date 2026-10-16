"""Create (or reset) an admin account. Prompts for the password so it never touches shell history.

    python -m scripts.create_admin you@example.com "Your Name"
"""
import getpass
import sys

from sqlalchemy import select

from app.core.crypto import blind_index
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import Role, Staff

if len(sys.argv) < 2:
    sys.exit("usage: python -m scripts.create_admin <email> [name]")
email = sys.argv[1].lower()
name = sys.argv[2] if len(sys.argv) > 2 else email.split("@")[0]
pw = getpass.getpass("Password (min 10 chars): ")
if len(pw) < 10 or pw != getpass.getpass("Repeat password: "):
    sys.exit("Passwords must match and be at least 10 characters.")
with SessionLocal() as db:
    s = db.scalar(select(Staff).where(Staff.email_hash == blind_index(email)))
    if s:
        s.password_hash, s.role, s.is_active = hash_password(pw), Role.admin, True
    else:
        db.add(Staff(email=email, name=name, role=Role.admin, password_hash=hash_password(pw)))
    db.commit()
    print("Admin ready:", email)
