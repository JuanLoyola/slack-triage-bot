"""Throttling per key, in memory — same honest-about-scale choice as the API.

The port lives in the domain so the use case can ask "is this author allowed
to spend tokens right now?" without knowing what a sliding window is.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from triage_bot.domain.ports import RateLimit


class SlidingWindowLimiter:
    """Allow at most `max_requests` per `window_seconds` for each key."""

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        clock=time.monotonic,
    ) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be >= 1")
        self._max = max_requests
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> RateLimit:
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            if len(hits) < self._max:
                hits.append(now)
                return RateLimit(allowed=True)
            retry_after = self._window - (now - hits[0])
            return RateLimit(allowed=False, retry_after_seconds=max(retry_after, 0.0))


class PermissiveRateLimiter:
    """Always allows — for tests and local runs that don't care about throttling."""

    def check(self, key: str) -> RateLimit:
        return RateLimit(allowed=True)
