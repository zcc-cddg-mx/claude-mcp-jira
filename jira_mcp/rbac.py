import os
from typing import Optional

ROLES: dict[str, list[str]] = {
    "dev":    ["create_jira_issue", "get_jira_issue", "search_jira_issues", "add_comment_jira_issue"],
    "lead":   ["create_jira_issue", "update_jira_issue", "get_jira_issue", "search_jira_issues", "add_comment_jira_issue", "assign_jira_issue", "set_priority_jira_issue"],
    "system": ["create_jira_issue", "update_jira_issue", "get_jira_issue", "search_jira_issues", "add_comment_jira_issue", "assign_jira_issue", "set_priority_jira_issue"],
}

# Map API key → role. Format: "key1:role1,key2:role2"
_KEY_ROLE_MAP: dict[str, str] = {}
for entry in os.environ.get("MCP_KEY_ROLES", "").split(","):
    if ":" in entry:
        k, r = entry.strip().split(":", 1)
        _KEY_ROLE_MAP[k.strip()] = r.strip()

_DEFAULT_ROLE = os.environ.get("MCP_DEFAULT_ROLE", "dev")


def role_for_key(api_key: Optional[str]) -> str:
    if not api_key:
        return _DEFAULT_ROLE
    return _KEY_ROLE_MAP.get(api_key, _DEFAULT_ROLE)


def check_permission(api_key: Optional[str], tool: str) -> None:
    role = role_for_key(api_key)
    allowed = ROLES.get(role, [])
    if tool not in allowed:
        raise PermissionError(f"Role '{role}' cannot invoke '{tool}'")
