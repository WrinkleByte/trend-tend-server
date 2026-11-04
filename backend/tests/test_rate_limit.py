# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

"""Rate limiter internals (2026-08-19 review, S11).

The limiter's own behaviour (429 after N) is exercised through the auth
endpoints; these cover the memory-growth fix, which has no HTTP surface.
"""

import asyncio

from app.core.rate_limit import RateLimiter


class _FakeClient:
    def __init__(self, host: str) -> None:
        self.host = host


class _FakeRequest:
    def __init__(self, host: str) -> None:
        self.client = _FakeClient(host)


async def test_expired_keys_are_swept_instead_of_accumulating():
    # One request each from many distinct IPs, none of which is ever seen
    # again -- the rotating-source-address case. Before the sweep, every key
    # stayed resident forever.
    # Sub-second window so the test doesn't have to actually wait around.
    limiter = RateLimiter(times=100, seconds=1)
    limiter.window_seconds = 0.05
    limiter._SWEEP_EVERY_N_CALLS = 50

    for i in range(200):
        await limiter(_FakeRequest(f"10.0.0.{i}"))

    # Age everything out of the window, then trip one more sweep.
    await asyncio.sleep(0.1)
    for i in range(60):
        await limiter(_FakeRequest(f"192.168.0.{i}"))

    # The 200 expired keys must be gone; only recent ones may remain.
    assert not any(key.startswith("10.0.0.") for key in limiter._hits)


async def test_sweep_does_not_drop_keys_still_inside_the_window():
    limiter = RateLimiter(times=100, seconds=60)
    limiter._SWEEP_EVERY_N_CALLS = 10

    await limiter(_FakeRequest("10.1.1.1"))
    for i in range(20):
        await limiter(_FakeRequest(f"10.2.2.{i}"))

    # 10.1.1.1 is still within its 60s window, so its budget must survive --
    # sweeping it would silently reset an active client's count.
    assert "10.1.1.1" in limiter._hits


async def test_limit_still_fires_after_a_sweep():
    from fastapi import HTTPException

    limiter = RateLimiter(times=3, seconds=60)
    limiter._SWEEP_EVERY_N_CALLS = 2

    for _ in range(3):
        await limiter(_FakeRequest("10.3.3.3"))

    try:
        await limiter(_FakeRequest("10.3.3.3"))
    except HTTPException as exc:
        assert exc.status_code == 429
    else:
        raise AssertionError("expected the 4th request to be rate limited")
