import time
from collections import defaultdict, deque
from threading import Lock


class RateLimiter:
    """Sliding-window rate limiter. Thread-safe."""

    def __init__(self, max_calls: int, window: int, label: str = "Rate limit") -> None:
        self._max_calls = max_calls
        self._window = window
        self._label = label
        self._buckets: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> None:
        """Raise RuntimeError if key has exceeded the limit."""
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] < now - self._window:
                bucket.popleft()
            if len(bucket) >= self._max_calls:
                raise RuntimeError(
                    f"{self._label} exceeded: max {self._max_calls} requests per {self._window}s"
                )
            bucket.append(now)
