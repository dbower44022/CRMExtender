"""Simple token-bucket rate limiter for API calls."""

from __future__ import annotations

import time


class RateLimiter:
    """Token-bucket rate limiter.

    Allows up to `rate` calls per second, with a burst capacity of `burst`.
    """

    def __init__(self, rate: float, burst: int | None = None) -> None:
        self.rate = rate
        self.burst = burst if burst is not None else max(1, int(rate))
        self.tokens = float(self.burst)
        self.last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_refill = now

    def acquire(self) -> None:
        """Block until a token is available."""
        while True:
            self._refill()
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return
            # Sleep for the time needed to generate one token
            deficit = 1.0 - self.tokens
            time.sleep(deficit / self.rate)
