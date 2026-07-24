from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.models import Base
from src.utils.caching import DBCache


def test_cache_operations():
    """Verify set, get, delete, and expiration in DBCache."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    cache = DBCache(session)

    # 1. Set & Get
    cache.set("test_key", {"data": 123}, ttl_seconds=10)
    assert cache.get("test_key") == {"data": 123}

    # 2. Key Delete
    cache.delete("test_key")
    assert cache.get("test_key") is None

    # 3. Expiration
    cache.set("expired_key", "hello", ttl_seconds=-1)  # Already expired
    assert cache.get("expired_key") is None

    session.close()
