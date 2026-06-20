import re

# Patterns that must never leave the corporate network toward Claude API
_PATTERNS = [
    (r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", "Bearer [REDACTED]"),
    (r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", "[EMAIL]"),
    (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP]"),
    (r"password\s*[=:]\s*\S+", "password=[REDACTED]"),
    (r"token\s*[=:]\s*\S+", "token=[REDACTED]"),
    (r"secret\s*[=:]\s*\S+", "secret=[REDACTED]"),
]


def sanitize(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text
