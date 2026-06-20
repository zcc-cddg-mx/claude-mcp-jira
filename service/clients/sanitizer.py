import re

# Patterns that must never leave the corporate network toward Claude API
_PATTERNS = [
    # Auth tokens
    (r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", "Bearer [REDACTED]"),
    (r"password\s*[=:]\s*\S+", "password=[REDACTED]"),
    (r"token\s*[=:]\s*\S+", "token=[REDACTED]"),
    (r"secret\s*[=:]\s*\S+", "secret=[REDACTED]"),
    # Emails
    (r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", "[EMAIL]"),
    # Private IP ranges (RFC 1918)
    (r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[PRIVATE-IP]"),
    (r"\b172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b", "[PRIVATE-IP]"),
    (r"\b192\.168\.\d{1,3}\.\d{1,3}\b", "[PRIVATE-IP]"),
    # Internal hostnames (*.zurich.com, *.internal, *.local)
    (r"\b[\w\-]+\.zurich\.com\b", "[INTERNAL-HOST]"),
    (r"\b[\w\-]+\.internal\b", "[INTERNAL-HOST]"),
    (r"\b[\w\-]+\.local\b", "[INTERNAL-HOST]"),
    # Stack traces — file paths that expose infra layout
    (r'File "[^"]*", line \d+', "File [REDACTED]"),
    (r"Traceback \(most recent call last\):.*", "Traceback [REDACTED]", ),
]


def sanitize(text: str) -> str:
    for item in _PATTERNS:
        pattern, replacement = item[0], item[1]
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE | re.DOTALL)
    return text
