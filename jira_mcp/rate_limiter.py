import os
import time
from collections import defaultdict, deque
from threading import Lock

_WINDOW = int(os.environ.get("MCP_RATE_LIMIT_WINDOW", "60"))
_MAX_CALLS = int(os.environ.get("MCP_RATE_LIMIT_MAX_CALLS", "10"))

_buckets: dict[str, deque] = defaultdict(deque)
_lock = Lock()


def check(key: str) -> None:
    """Raise RuntimeError if the key has exceeded MCP-level rate limit."""
    now = time.monotonic()
    with _lock:
        bucket = _buckets[key]
        while bucket and bucket[0] < now - _WINDOW:
            bucket.popleft()
        if len(bucket) >= _MAX_CALLS:
            raise RuntimeError(
                f"MCP rate limit exceeded: max {_MAX_CALLS} calls per {_WINDOW}s"
            )
        bucket.append(now)
