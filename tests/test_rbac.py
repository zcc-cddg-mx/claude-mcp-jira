import importlib
import os

import pytest


def _reload_rbac(env: dict):
    for k, v in env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    import jira_mcp.rbac as mod
    importlib.reload(mod)
    return mod


# ── role_for_key ──────────────────────────────────────────────────────────────

def test_no_key_returns_default_role():
    mod = _reload_rbac({"MCP_DEFAULT_ROLE": "dev", "MCP_KEY_ROLES": ""})
    assert mod.role_for_key(None) == "dev"


def test_known_key_returns_mapped_role():
    mod = _reload_rbac({"MCP_KEY_ROLES": "keyA:lead,keyB:system", "MCP_DEFAULT_ROLE": "dev"})
    assert mod.role_for_key("keyA") == "lead"
    assert mod.role_for_key("keyB") == "system"


def test_unknown_key_returns_default():
    mod = _reload_rbac({"MCP_KEY_ROLES": "keyA:lead", "MCP_DEFAULT_ROLE": "dev"})
    assert mod.role_for_key("unknown") == "dev"


# ── check_permission ──────────────────────────────────────────────────────────

def test_dev_can_create():
    mod = _reload_rbac({"MCP_DEFAULT_ROLE": "dev", "MCP_KEY_ROLES": ""})
    mod.check_permission(None, "create_jira_issue")  # no raise


def test_dev_can_get():
    mod = _reload_rbac({"MCP_DEFAULT_ROLE": "dev", "MCP_KEY_ROLES": ""})
    mod.check_permission(None, "get_jira_issue")


def test_dev_can_search():
    mod = _reload_rbac({"MCP_DEFAULT_ROLE": "dev", "MCP_KEY_ROLES": ""})
    mod.check_permission(None, "search_jira_issues")


def test_dev_cannot_update():
    mod = _reload_rbac({"MCP_DEFAULT_ROLE": "dev", "MCP_KEY_ROLES": ""})
    with pytest.raises(PermissionError, match="Role 'dev' cannot invoke 'update_jira_issue'"):
        mod.check_permission(None, "update_jira_issue")


def test_lead_can_update():
    mod = _reload_rbac({"MCP_KEY_ROLES": "lead-key:lead", "MCP_DEFAULT_ROLE": "dev"})
    mod.check_permission("lead-key", "update_jira_issue")  # no raise


def test_system_can_all_tools():
    mod = _reload_rbac({"MCP_KEY_ROLES": "sys-key:system", "MCP_DEFAULT_ROLE": "dev"})
    for tool in ["create_jira_issue", "update_jira_issue", "get_jira_issue", "search_jira_issues"]:
        mod.check_permission("sys-key", tool)  # no raise


def test_unknown_role_blocks_all():
    mod = _reload_rbac({"MCP_DEFAULT_ROLE": "ghost", "MCP_KEY_ROLES": ""})
    with pytest.raises(PermissionError):
        mod.check_permission(None, "create_jira_issue")


def test_unknown_tool_raises():
    mod = _reload_rbac({"MCP_DEFAULT_ROLE": "lead", "MCP_KEY_ROLES": ""})
    with pytest.raises(PermissionError):
        mod.check_permission(None, "delete_everything")
