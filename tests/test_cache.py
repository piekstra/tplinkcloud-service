import asyncio

import pytest

from app.cache import SessionCache


async def test_lock_is_released_when_factory_raises():
    """A failing factory (e.g. an invalid token) must not leak a lock entry;
    otherwise anonymous callers with garbage tokens grow _locks without bound."""
    cache = SessionCache(maxsize=8, ttl=60)

    async def boom():
        raise ValueError("bad token")

    async def attempt():
        with pytest.raises(ValueError):
            await cache.get_or_create("garbage", boom)

    # Fire several concurrent attempts with the same failing token
    await asyncio.gather(*(attempt() for _ in range(5)))

    assert len(cache._locks) == 0


async def test_successful_factory_runs_once_under_concurrency():
    cache = SessionCache(maxsize=8, ttl=60)
    calls = 0

    async def factory():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return object()

    results = await asyncio.gather(*(cache.get_or_create("tok", factory) for _ in range(5)))

    # One build shared by all concurrent callers, and no leaked lock
    assert calls == 1
    assert all(r is results[0] for r in results)
    assert len(cache._locks) == 0
