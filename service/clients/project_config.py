import os
from typing import Optional

# Allowed projects — validated at request time; Claude/user input never bypasses this.
# Format: comma-separated list, e.g. "ZNRX,AIPROJECTS,SCRX"
_ALLOWED_RAW = os.environ.get("JIRA_ALLOWED_PROJECTS", os.environ.get("JIRA_PROJECT_KEY", ""))
ALLOWED_PROJECTS: list[str] = [p.strip() for p in _ALLOWED_RAW.split(",") if p.strip()]

_DEFAULT_PROJECT = os.environ.get("JIRA_DEFAULT_PROJECT", ALLOWED_PROJECTS[0] if ALLOWED_PROJECTS else "")

# Per-project field constraints derived from docs/jira-fields.md.
# priority_format: "id" → must use numeric ID; "name" → plain name accepted.
# required_custom: extra fields injected on creation.
# issuetype_fallback: map unsupported types to a safe alternative.
# ticket_lang: default language for Claude-generated content.
_PROJECT_CONFIGS: dict[str, dict] = {
    "ZNRX": {
        "priority_format": "id",
        "priority_ids": {"Highest": "1", "High": "2", "Low": "4"},
        "required_custom": {"customfield_25832": {"id": "44461"}},
        "issuetype_fallback": {"Bug": "Task", "Improvement": "Task"},
        "ticket_lang": "es",
    },
    "AIPROJECTS": {
        "priority_format": "name",
        "priority_ids": {},
        "required_custom": {},
        "issuetype_fallback": {},
        "ticket_lang": "en",
    },
    "SCRX": {
        "priority_format": "name",
        "priority_ids": {},
        "required_custom": {},
        "issuetype_fallback": {},
        "ticket_lang": "es",
    },
}

# Fallback config used for any project not explicitly listed above.
_DEFAULT_CONFIG: dict = {
    "priority_format": "name",
    "priority_ids": {},
    "required_custom": {},
    "issuetype_fallback": {},
    "ticket_lang": os.environ.get("TICKET_LANG", "es"),
}


def get_config(project_key: str) -> dict:
    return _PROJECT_CONFIGS.get(project_key.upper(), _DEFAULT_CONFIG)


def resolve_project(requested: Optional[str]) -> str:
    """Return the effective project key, validating against JIRA_ALLOWED_PROJECTS."""
    key = (requested or _DEFAULT_PROJECT).upper()
    if ALLOWED_PROJECTS and key not in ALLOWED_PROJECTS:
        allowed = ", ".join(ALLOWED_PROJECTS)
        raise ValueError(f"Project '{key}' not in allowed list: {allowed}")
    return key
