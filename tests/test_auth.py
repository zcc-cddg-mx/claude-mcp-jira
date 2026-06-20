import importlib
import os

import pytest


def _reload_auth(env: dict):
    """Reload jira_mcp.auth with patched env vars."""
    for k, v in env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    import jira_mcp.auth as mod
    importlib.reload(mod)
    return mod


# ── verify_api_key ────────────────────────────────────────────────────────────

def test_dev_mode_no_key_configured():
    mod = _reload_auth({"MCP_API_KEY": ""})
    mod.verify_api_key(None)   # should not raise
    mod.verify_api_key("anything")  # should not raise


def test_valid_key_accepted():
    mod = _reload_auth({"MCP_API_KEY": "secret123"})
    mod.verify_api_key("secret123")  # no raise


def test_invalid_key_raises():
    mod = _reload_auth({"MCP_API_KEY": "secret123"})
    with pytest.raises(PermissionError, match="Invalid API key"):
        mod.verify_api_key("wrong")


def test_none_key_raises_when_configured():
    mod = _reload_auth({"MCP_API_KEY": "secret123"})
    with pytest.raises(PermissionError):
        mod.verify_api_key(None)


# ── verify_ip ─────────────────────────────────────────────────────────────────

def test_ip_in_allowed_range():
    mod = _reload_auth({"MCP_ALLOWED_CIDRS": "10.0.0.0/8"})
    mod.verify_ip("10.1.2.3")  # no raise


def test_ip_outside_range_raises():
    mod = _reload_auth({"MCP_ALLOWED_CIDRS": "10.0.0.0/8"})
    with pytest.raises(PermissionError, match="IP not allowed"):
        mod.verify_ip("8.8.8.8")


def test_ip_multiple_cidrs():
    mod = _reload_auth({"MCP_ALLOWED_CIDRS": "10.0.0.0/8,192.168.0.0/16"})
    mod.verify_ip("192.168.1.100")  # no raise
    with pytest.raises(PermissionError):
        mod.verify_ip("172.16.0.1")


def test_no_ip_configured_allows_all():
    mod = _reload_auth({"MCP_ALLOWED_CIDRS": ""})
    mod.verify_ip("8.8.8.8")  # no raise — dev mode


def test_invalid_ip_format_raises():
    mod = _reload_auth({"MCP_ALLOWED_CIDRS": "10.0.0.0/8"})
    with pytest.raises(PermissionError, match="Invalid IP"):
        mod.verify_ip("not-an-ip")


def test_none_ip_allowed_when_networks_configured():
    mod = _reload_auth({"MCP_ALLOWED_CIDRS": "10.0.0.0/8"})
    mod.verify_ip(None)  # no raise — client IP unknown, allow through
