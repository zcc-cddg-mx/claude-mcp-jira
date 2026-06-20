import pytest
from service.clients.sanitizer import sanitize


def test_bearer_token_redacted():
    assert sanitize("Authorization: Bearer abc123xyz") == "Authorization: Bearer [REDACTED]"


def test_password_redacted():
    assert "[REDACTED]" in sanitize("password=s3cr3t")
    assert "[REDACTED]" in sanitize("password: s3cr3t")


def test_token_redacted():
    assert "[REDACTED]" in sanitize("token=eyJhbGc...")


def test_secret_redacted():
    assert "[REDACTED]" in sanitize("secret=abc")


def test_email_redacted():
    result = sanitize("contact user@example.com for help")
    assert "user@example.com" not in result
    assert "[EMAIL]" in result


def test_private_ip_10_redacted():
    assert "[PRIVATE-IP]" in sanitize("server at 10.0.1.50")


def test_private_ip_172_redacted():
    assert "[PRIVATE-IP]" in sanitize("host: 172.16.0.1")


def test_private_ip_192_redacted():
    assert "[PRIVATE-IP]" in sanitize("gateway 192.168.1.1")


def test_public_ip_not_redacted():
    result = sanitize("request from 8.8.8.8")
    assert "8.8.8.8" in result


def test_internal_hostname_redacted():
    assert "[INTERNAL-HOST]" in sanitize("connect to jira.zurich.com")
    assert "[INTERNAL-HOST]" in sanitize("service.internal")
    assert "[INTERNAL-HOST]" in sanitize("dev.local")


def test_stack_trace_redacted():
    trace = 'File "/app/service/main.py", line 42, in create'
    assert "File [REDACTED]" in sanitize(trace)


def test_plain_text_unchanged():
    text = "crear tarea de alta prioridad para revisar el módulo de pagos"
    assert sanitize(text) == text


def test_multiple_patterns_in_one_string():
    text = "error en 192.168.0.1 con token=abc123 — user@corp.com"
    result = sanitize(text)
    assert "192.168.0.1" not in result
    assert "abc123" not in result
    assert "user@corp.com" not in result
