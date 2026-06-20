import os

from shared.rate_limiter import RateLimiter

_limiter = RateLimiter(
    max_calls=int(os.environ.get("RATE_LIMIT_MAX_CALLS", "30")),
    window=int(os.environ.get("RATE_LIMIT_WINDOW", "60")),
    label="Rate limit",
)

check = _limiter.check
