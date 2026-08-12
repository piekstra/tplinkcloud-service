import asyncio
import hashlib
from collections.abc import Awaitable, Callable

from cachetools import TTLCache


class SessionCache:
    """TTL cache of per-token sessions, keyed by a token digest.

    A per-key lock prevents a stampede of TP-Link cloud fetches when several
    requests arrive for the same token at once (the UI fires its devices and
    power queries together).
    """

    def __init__(self, maxsize: int, ttl: int):
        self._cache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._locks: dict[str, asyncio.Lock] = {}

    @staticmethod
    def _key(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()[:16]

    async def get_or_create(self, token: str, factory: Callable[[], Awaitable]):
        key = self._key(token)
        session = self._cache.get(key)
        if session is not None:
            return session

        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            session = self._cache.get(key)
            if session is None:
                session = await factory()
                self._cache[key] = session
            self._locks.pop(key, None)
        return session
