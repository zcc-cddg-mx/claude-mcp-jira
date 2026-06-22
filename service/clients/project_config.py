"""
Thin facade over project_db — keeps the same public API so callers don't change.

  get_config(key)       → dict with project constraints (from DB or auto-discovered)
  resolve_project(key)  → validated project key (raises ValueError if Jira 404)
"""

import os
from typing import Optional

from .project_db import get_or_discover

_DEFAULT_PROJECT = os.environ.get("JIRA_DEFAULT_PROJECT", os.environ.get("JIRA_PROJECT_KEY", ""))

# JIRA_ALLOWED_PROJECTS is now advisory — it gates which projects users can send
# via the API. If empty, any project that exists in Jira is allowed.
_ALLOWED_RAW = os.environ.get("JIRA_ALLOWED_PROJECTS", "")
ALLOWED_PROJECTS: list[str] = [p.strip().upper() for p in _ALLOWED_RAW.split(",") if p.strip()]


def get_config(project_key: str) -> dict:
    """Return config for project_key, auto-discovering from Jira if needed."""
    return get_or_discover(project_key.upper())


def resolve_project(requested: Optional[str]) -> str:
    """
    Resolve and validate the effective project key.
    - If JIRA_ALLOWED_PROJECTS is set, project must be in the list.
    - Always verifies the project exists in Jira (via get_or_discover).
    Raises ValueError on invalid or nonexistent project.
    """
    key = (requested or _DEFAULT_PROJECT).upper()
    if ALLOWED_PROJECTS and key not in ALLOWED_PROJECTS:
        allowed = ", ".join(ALLOWED_PROJECTS)
        raise ValueError(f"Project '{key}' not in allowed list: {allowed}")
    # This call verifies existence in Jira and populates the DB if needed
    get_or_discover(key)
    return key
