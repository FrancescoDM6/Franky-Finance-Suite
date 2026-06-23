"""Thread-safe bounded caches used by the Research module."""

import threading
import time
from collections import OrderedDict
from typing import Any, Optional

OPTIONS_CACHE_TTL = 300
OPTIONS_CACHE_MAX_SIZE = 100


class LRUCache:
    """Thread-safe LRU cache with TTL support for options data.

    Prevents unbounded memory growth by evicting least recently used entries
    when max_size is reached. Also evicts entries older than TTL.
    """

    def __init__(
        self, max_size: int = OPTIONS_CACHE_MAX_SIZE, ttl: int = OPTIONS_CACHE_TTL
    ):
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[dict]:
        """Get item from cache, returns None if not found or expired."""
        with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]

            # Check TTL
            if time.time() - entry.get("timestamp", 0) > self._ttl:
                del self._cache[key]
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return entry.get("data")

    def set(self, key: str, data: Any) -> None:
        """Set item in cache, evicting LRU entries if needed."""
        with self._lock:
            # Remove if exists (will be re-added at end)
            if key in self._cache:
                del self._cache[key]

            # Evict oldest entries if at capacity
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)

            # Add new entry
            self._cache[key] = {
                "data": data,
                "timestamp": time.time(),
            }

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """Current cache size."""
        return len(self._cache)

