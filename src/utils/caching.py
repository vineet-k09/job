import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from src.db.models import CacheEntry


class DBCache:
    """
    SQLite/SQLAlchemy-based cache provider with support for TTL (Time To Live).
    """

    def __init__(self, session: Session):
        self.session = session

    def get(self, key: str) -> Any | None:
        """
        Retrieves a cached value if it exists and is not expired.
        """
        entry = self.session.query(CacheEntry).filter(CacheEntry.key == key).first()
        if not entry:
            return None

        if entry.expires_at < datetime.utcnow():
            # Clean up expired entry
            self.session.delete(entry)
            self.session.commit()
            return None

        try:
            return json.loads(entry.value)
        except json.JSONDecodeError:
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """
        Stores a value in the cache with a TTL (Time To Live) in seconds.
        """
        serialized_val = json.dumps(value)
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)

        entry = self.session.query(CacheEntry).filter(CacheEntry.key == key).first()
        if entry:
            entry.value = serialized_val
            entry.expires_at = expires_at
        else:
            entry = CacheEntry(key=key, value=serialized_val, expires_at=expires_at)
            self.session.add(entry)

        self.session.commit()

    def delete(self, key: str) -> None:
        """Deletes a key from the cache."""
        entry = self.session.query(CacheEntry).filter(CacheEntry.key == key).first()
        if entry:
            self.session.delete(entry)
            self.session.commit()

    def clear_expired(self) -> int:
        """Deletes all expired cache entries and returns the count."""
        now = datetime.utcnow()
        expired = (
            self.session.query(CacheEntry).filter(CacheEntry.expires_at < now).all()
        )
        count = len(expired)
        for entry in expired:
            self.session.delete(entry)
        if count > 0:
            self.session.commit()
        return count
