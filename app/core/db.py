from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
_kw = {} if _settings.database_url.startswith("sqlite") else {"pool_size": 5, "max_overflow": 5}
# pool_recycle (not pool_pre_ping): pre-ping costs one extra database round trip on every request.
engine = create_engine(_settings.database_url, pool_recycle=240, **_kw)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
