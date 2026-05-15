"""Generic DuckDB-backed cache service with TTL support.

Centralizes caching logic previously embedded in MarketDataService.
Provides configurable TTLs per data type.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import asdict
from typing import Any, Optional
import threading

from ..core.database import get_database_manager
from ..core.metrics import record_cache_hit, record_cache_miss

logger = logging.getLogger(__name__)


# Default TTLs (in minutes) per data type
DEFAULT_TTLS = {
    "ticker_info": 5,
    "price_range": 5,
    "news": 30,
    "analyst": 60,
    "sentiment": 15,
}


class CacheService:
    """DuckDB-backed cache with TTL support.

    Usage:
        cache = get_cache_service()

        # Check cache first
        data = cache.get("AAPL", "ticker_info")
        if data is None:
            data = fetch_from_api()
            cache.set("AAPL", "ticker_info", data)
    """

    _instance: Optional["CacheService"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "CacheService":
        """Thread-safe singleton with double-checked locking."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._db = get_database_manager()
        self._initialized = True

    def get(self, key: str, data_type: str) -> Optional[dict]:
        """Get cached data if not expired.

        Args:
            key: Cache key (e.g., ticker symbol)
            data_type: Type of data (e.g., "ticker_info", "news")

        Returns:
            Cached dict data or None if miss/expired
        """
        try:
            query = """
                SELECT data FROM market_data_cache 
                WHERE ticker_symbol = ? AND data_type = ? AND expires_at > CURRENT_TIMESTAMP
            """
            result = self._db.query(query, (key.upper(), data_type))
            if result:
                data_val = result[0]["data"]
                record_cache_hit(data_type)
                if isinstance(data_val, str):
                    return json.loads(data_val)
                return data_val
            else:
                record_cache_miss(data_type)
        except Exception as e:
            logger.warning("Cache read error for %s/%s: %s", key, data_type, e)
            record_cache_miss(data_type)
        return None

    def set(
        self, key: str, data_type: str, data: Any, ttl_minutes: Optional[int] = None
    ):
        """Store data in cache with TTL.

        Args:
            key: Cache key (e.g., ticker symbol)
            data_type: Type of data
            data: Data to cache (dict or dataclass)
            ttl_minutes: TTL override (uses default for data_type if None)
        """
        try:
            ttl = ttl_minutes or DEFAULT_TTLS.get(data_type, 5)
            now_utc = datetime.now(timezone.utc)
            expires_at = now_utc + timedelta(minutes=ttl)

            # Serialize dataclass if needed
            if hasattr(data, "__dataclass_fields__"):
                data_dict = asdict(data)
            else:
                data_dict = data

            # The schema defines id with DEFAULT nextval('market_data_cache_id_seq')
            # and UNIQUE(ticker_symbol, data_type), so omit id entirely and let
            # the sequence assign it. The previous code passed a random int32 as
            # the PK, which eventually collides by birthday paradox; DuckDB 1.5.x
            # then throws an unhandled C++ FatalException during commit cleanup
            # which terminate()s the entire worker process.
            query = """
                INSERT INTO market_data_cache
                (ticker_symbol, data_type, data, expires_at, cached_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (ticker_symbol, data_type) DO UPDATE SET
                    data = excluded.data,
                    expires_at = excluded.expires_at,
                    cached_at = excluded.cached_at
            """

            self._db.execute(
                query,
                (
                    key.upper(),
                    data_type,
                    json.dumps(data_dict),
                    expires_at,
                    now_utc,
                ),
            )
        except Exception as e:
            logger.warning("Cache write error for %s/%s: %s", key, data_type, e)

    def invalidate(self, key: str, data_type: Optional[str] = None):
        """Invalidate cache entries.

        Args:
            key: Cache key
            data_type: Specific type to invalidate (all if None)
        """
        try:
            if data_type:
                self._db.execute(
                    "DELETE FROM market_data_cache WHERE ticker_symbol = ? AND data_type = ?",
                    (key.upper(), data_type),
                )
            else:
                self._db.execute(
                    "DELETE FROM market_data_cache WHERE ticker_symbol = ?",
                    (key.upper(),),
                )
        except Exception as e:
            logger.warning("Cache invalidate error for %s: %s", key, e)

    def clear_expired(self):
        """Remove all expired cache entries."""
        try:
            self._db.execute(
                "DELETE FROM market_data_cache WHERE expires_at < CURRENT_TIMESTAMP"
            )
        except Exception as e:
            logger.warning("Cache cleanup error: %s", e)

    def health_check(self) -> bool:
        """Check if cache is operational."""
        try:
            self._db.query("SELECT 1 FROM market_data_cache LIMIT 1")
            return True
        except Exception:
            return False


def get_cache_service() -> CacheService:
    """Get singleton cache service instance."""
    return CacheService()
