# SPDX-FileCopyrightText: 2026 WrinkleByte LLC
# SPDX-License-Identifier: AGPL-3.0-only

import time
from typing import ClassVar

from fastapi import HTTPException, Request, status


class RateLimiter:
    """In-memory sliding-window rate limiter, keyed by client IP.

    Single-process only (state lives in this instance's own dict) --
    matches this app's single-uvicorn-worker deployment (see the
    Dockerfile's `CMD`, no `--workers`). Doesn't consult
    X-Forwarded-For: trusting that header without a configured
    trusted-proxy allowlist would let any client bypass the limit just by
    setting it themselves, which is the worse failure mode for the common
    case of a directly-exposed instance. A deployment sitting behind a
    reverse proxy will see all of its traffic share one bucket instead --
    a known limitation, not a bug.

    Used as a FastAPI dependency (`Depends(some_limiter)`); construct one
    instance per distinct limit and share it across every route that
    limit applies to.
    """

    _all_instances: ClassVar[list["RateLimiter"]] = []

    # How many requests may pass before sweeping expired keys. Stale entries
    # were previously pruned only when that same IP was seen again, so an
    # attacker rotating source addresses -- trivial across an IPv6 /64 --
    # grew _hits without bound, a slow memory exhaustion against the single
    # worker this whole design assumes (review S11). Amortised: the sweep is
    # O(keys) but runs once per this many calls, not per call.
    _SWEEP_EVERY_N_CALLS = 1000

    def __init__(self, times: int, seconds: int) -> None:
        self.times = times
        self.window_seconds = seconds
        self._hits: dict[str, list[float]] = {}
        self._calls_since_sweep = 0
        RateLimiter._all_instances.append(self)

    def _sweep(self, cutoff: float) -> None:
        """Drop every key whose hits have all aged out of the window."""
        for key in [k for k, hits in self._hits.items() if not hits or hits[-1] < cutoff]:
            del self._hits[key]

    def reset(self) -> None:
        """Test-only hook -- see conftest.py's autouse reset fixture."""
        self._hits.clear()
        self._calls_since_sweep = 0

    async def __call__(self, request: Request) -> None:
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        cutoff = now - self.window_seconds

        self._calls_since_sweep += 1
        if self._calls_since_sweep >= self._SWEEP_EVERY_N_CALLS:
            self._calls_since_sweep = 0
            self._sweep(cutoff)

        hits = self._hits.get(key)
        if hits is not None:
            while hits and hits[0] < cutoff:
                hits.pop(0)
            if not hits:
                # Drop the now-empty entry rather than letting the dict
                # grow forever with one stale key per IP ever seen.
                del self._hits[key]
                hits = None

        if hits is not None and len(hits) >= self.times:
            retry_after = int(hits[0] + self.window_seconds - now) + 1
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many requests. Please try again later.",
                headers={"Retry-After": str(max(retry_after, 1))},
            )

        self._hits.setdefault(key, []).append(now)


def reset_all_rate_limiters() -> None:
    """Test-only hook -- see conftest.py's autouse reset fixture."""
    for limiter in RateLimiter._all_instances:
        limiter.reset()
