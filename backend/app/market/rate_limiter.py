import asyncio
import time
from typing import List, Tuple
from app.market.constants import DEFAULT_MAX_WEIGHT_PER_MINUTE


class AsyncRateLimiter:
    """
    Sliding window rate limiter for Binance REST requests.
    Prevents IP ban and 429 HTTP errors by pacing requests.
    """
    def __init__(self, max_weight_per_minute: int = DEFAULT_MAX_WEIGHT_PER_MINUTE):
        self.max_weight = max_weight_per_minute
        self.window_seconds = 60.0
        # List of (timestamp, weight)
        self.requests: List[Tuple[float, int]] = []
        self._lock = asyncio.Lock()

    async def acquire(self, weight: int = 2) -> None:
        """Acquire permission to execute a request with given weight."""
        async with self._lock:
            while True:
                now = time.monotonic()
                # Prune requests outside the current 60s sliding window
                cutoff = now - self.window_seconds
                self.requests = [r for r in self.requests if r[0] > cutoff]

                current_weight = sum(r[1] for r in self.requests)
                if current_weight + weight <= self.max_weight:
                    self.requests.append((now, weight))
                    return

                # Calculate sleep duration until earliest request drops off window
                oldest_timestamp = self.requests[0][0]
                sleep_duration = (oldest_timestamp + self.window_seconds) - now + 0.1
                if sleep_duration > 0:
                    await asyncio.sleep(sleep_duration)

    def remaining_weight(self) -> int:
        """Returns approximate remaining weight available in the current window."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        active = [r for r in self.requests if r[0] > cutoff]
        used = sum(r[1] for r in active)
        return max(0, self.max_weight - used)
