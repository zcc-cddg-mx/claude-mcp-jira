import os

from shared.rate_limiter import RateLimiter

_limiter = RateLimiter(
    max_calls=int(os.environ.get("MCP_RATE_LIMIT_MAX_CALLS", "10")),
    window=int(os.environ.get("MCP_RATE_LIMIT_WINDOW", "60")),
    label="MCP rate limit",
)

check = _limiter.check
