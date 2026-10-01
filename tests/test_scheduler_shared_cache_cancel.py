"""Shared scheduler cache cancellation must not poison other callers."""

import asyncio


def test_cancelled_fetch_owner_releases_pending_and_retry_works():
    from src import task_scheduler

    async def drive():
        task_scheduler._shared_cache.clear()
        task_scheduler._shared_cache_pending.clear()
        started = asyncio.Event()
        release = asyncio.Event()

        async def fetch():
            started.set()
            await release.wait()
            return "fresh"

        owner = asyncio.create_task(task_scheduler._cached(("owner-cancel",), 60, fetch))
        await started.wait()
        waiter = asyncio.create_task(task_scheduler._cached(("owner-cancel",), 60, fetch))
        owner.cancel()
        try:
            await owner
        except asyncio.CancelledError:
            pass
        try:
            await waiter
        except asyncio.CancelledError:
            pass
        assert ("owner-cancel",) not in task_scheduler._shared_cache_pending

        assert await task_scheduler._cached(("owner-cancel",), 60, lambda: _ready("retry")) == "retry"

    async def _ready(value):
        return value

    asyncio.run(drive())


def test_cancelled_waiter_does_not_cancel_shared_fetch():
    from src import task_scheduler

    async def drive():
        task_scheduler._shared_cache.clear()
        task_scheduler._shared_cache_pending.clear()
        release = asyncio.Event()
        calls = 0

        async def fetch():
            nonlocal calls
            calls += 1
            await release.wait()
            return "shared"

        owner = asyncio.create_task(task_scheduler._cached(("waiter-cancel",), 60, fetch))
        while ("waiter-cancel",) not in task_scheduler._shared_cache_pending:
            await asyncio.sleep(0)
        waiter = asyncio.create_task(task_scheduler._cached(("waiter-cancel",), 60, fetch))
        waiter.cancel()
        try:
            await waiter
        except asyncio.CancelledError:
            pass
        release.set()
        assert await owner == "shared"
        assert calls == 1

    asyncio.run(drive())
