"""A tiny Redis look-alike (strings, counters, TTLs, SET NX) driven by the injected Clock.

Only what the services need: get/set/setex/delete/exists/incr/expire/ttl/keys. Values are stored as
strings, like real Redis, so callers must serialize structured data themselves (see
`nyc_health.db.codec`). Expiry is evaluated lazily against `clock.now()`, so tests can advance a
FrozenClock to expire keys.
"""
import fnmatch
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from nyc_health.core.clock import Clock


class FakeRedis:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._lock = threading.RLock()
        self._data: Dict[str, Tuple[str, Optional[datetime]]] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            value = self._live(key)
            if value is None:
                self.misses += 1
            else:
                self.hits += 1
            return value

    def set(self, key: str, value, ex: Optional[int] = None, nx: bool = False) -> bool:
        """SET with optional TTL (`ex`, seconds) and NX (only set if absent). Returns True if written."""
        with self._lock:
            if nx and self._live(key) is not None:
                return False
            expires_at = self._clock.now() + timedelta(seconds=ex) if ex else None
            self._data[key] = (str(value), expires_at)
            return True

    def setex(self, key: str, seconds: int, value) -> bool:
        return self.set(key, value, ex=seconds)

    def delete(self, *keys: str) -> int:
        with self._lock:
            removed = 0
            for key in keys:
                if self._live(key) is not None:
                    del self._data[key]
                    removed += 1
            return removed

    def exists(self, key: str) -> bool:
        with self._lock:
            return self._live(key) is not None

    def incr(self, key: str, amount: int = 1) -> int:
        with self._lock:
            current = self._live(key)
            expires_at = self._data[key][1] if current is not None else None
            new_value = int(current or 0) + amount
            self._data[key] = (str(new_value), expires_at)
            return new_value

    def expire(self, key: str, seconds: int) -> bool:
        with self._lock:
            value = self._live(key)
            if value is None:
                return False
            self._data[key] = (value, self._clock.now() + timedelta(seconds=seconds))
            return True

    def ttl(self, key: str) -> int:
        """Seconds to live; -1 if the key has no expiry, -2 if it does not exist."""
        with self._lock:
            if self._live(key) is None:
                return -2
            expires_at = self._data[key][1]
            if expires_at is None:
                return -1
            return int((expires_at - self._clock.now()).total_seconds())

    def keys(self, pattern: str = "*") -> List[str]:
        with self._lock:
            return sorted(k for k in list(self._data) if self._live(k) is not None and fnmatch.fnmatch(k, pattern))

    def flushall(self) -> None:
        with self._lock:
            self._data.clear()

    def _live(self, key: str) -> Optional[str]:
        entry = self._data.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and self._clock.now() >= expires_at:
            del self._data[key]
            return None
        return value
