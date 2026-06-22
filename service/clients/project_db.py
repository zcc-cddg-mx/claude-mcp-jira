"""
SQLite-backed project registry with lazy auto-discovery.

On first access to an unknown project key, the system queries Jira to verify
the project exists and discovers what fields it can, then stores the config.
Subsequent accesses are served from the local DB — no extra Jira calls.

Schema (single table):
  project_key        TEXT PRIMARY KEY
  priority_format    TEXT   — "id" | "name"
  priority_ids_json  TEXT   — JSON object  {"Highest":"1", ...}
  required_custom_json TEXT — JSON object  {"customfield_25832":{"id":"44461"}}
  issuetype_fallback_json TEXT — JSON object {"Bug":"Task"}
  ticket_lang        TEXT   — "es" | "en"
  discovered_at      TEXT   — ISO timestamp of last discovery/update
  discovery_source   TEXT   — "seed" | "jira_auto" | "jira_createmeta"
"""

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional

import requests

_logger = logging.getLogger(__name__)

_DB_PATH = os.environ.get("PROJECT_DB_PATH", "projects.db")
_JIRA_URL = os.environ.get("JIRA_URL", "").rstrip("/")
_JIRA_PAT = os.environ.get("JIRA_PAT", "")
_CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE", True)
_TIMEOUT = int(os.environ.get("JIRA_TIMEOUT", "30"))

_HEADERS = {
    "Authorization": f"Bearer {_JIRA_PAT}",
    "Accept": "application/json",
}

_DEFAULT_LANG = os.environ.get("TICKET_LANG", "es")

_DEFAULT_CONFIG: dict = {
    "priority_format": "name",
    "priority_ids": {},
    "required_custom": {},
    "issuetype_fallback": {},
    "ticket_lang": _DEFAULT_LANG,
    "discovery_source": "default",
}

# Thread lock — SQLite writes are synchronous and infrequent (once per new project).
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _lock, _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                project_key           TEXT PRIMARY KEY,
                priority_format       TEXT NOT NULL DEFAULT 'name',
                priority_ids_json     TEXT NOT NULL DEFAULT '{}',
                required_custom_json  TEXT NOT NULL DEFAULT '{}',
                issuetype_fallback_json TEXT NOT NULL DEFAULT '{}',
                ticket_lang           TEXT NOT NULL DEFAULT 'es',
                discovered_at         TEXT NOT NULL,
                discovery_source      TEXT NOT NULL DEFAULT 'seed'
            )
        """)
        c.commit()


def _row_to_config(row: sqlite3.Row) -> dict:
    return {
        "priority_format": row["priority_format"],
        "priority_ids": json.loads(row["priority_ids_json"]),
        "required_custom": json.loads(row["required_custom_json"]),
        "issuetype_fallback": json.loads(row["issuetype_fallback_json"]),
        "ticket_lang": row["ticket_lang"],
        "discovery_source": row["discovery_source"],
    }


def _upsert(key: str, cfg: dict, source: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _lock, _conn() as c:
        c.execute("""
            INSERT INTO projects
                (project_key, priority_format, priority_ids_json,
                 required_custom_json, issuetype_fallback_json,
                 ticket_lang, discovered_at, discovery_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_key) DO UPDATE SET
                priority_format        = excluded.priority_format,
                priority_ids_json      = excluded.priority_ids_json,
                required_custom_json   = excluded.required_custom_json,
                issuetype_fallback_json= excluded.issuetype_fallback_json,
                ticket_lang            = excluded.ticket_lang,
                discovered_at          = excluded.discovered_at,
                discovery_source       = excluded.discovery_source
        """, (
            key,
            cfg["priority_format"],
            json.dumps(cfg["priority_ids"]),
            json.dumps(cfg["required_custom"]),
            json.dumps(cfg["issuetype_fallback"]),
            cfg.get("ticket_lang", _DEFAULT_LANG),
            now,
            source,
        ))
        c.commit()


def _get_from_db(key: str) -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM projects WHERE project_key = ?", (key,)
        ).fetchone()
    return _row_to_config(row) if row else None


def _discover_from_jira(key: str) -> dict:
    """
    Query Jira to verify the project exists and infer its config.
    Raises ValueError if the project does not exist in Jira.
    Returns a config dict (best-effort; falls back to defaults for unknown fields).
    """
    # Verify project exists
    r = requests.get(
        f"{_JIRA_URL}/rest/api/2/project/{key}",
        headers=_HEADERS,
        verify=_CA_BUNDLE,
        timeout=_TIMEOUT,
    )
    if r.status_code == 404:
        raise ValueError(f"Project '{key}' does not exist in Jira")
    r.raise_for_status()

    cfg = {
        "priority_format": "name",
        "priority_ids": {},
        "required_custom": {},
        "issuetype_fallback": {},
        "ticket_lang": _DEFAULT_LANG,
    }
    source = "jira_auto"

    # Try createmeta to detect required fields (may not be available with all PATs)
    try:
        cm = requests.get(
            f"{_JIRA_URL}/rest/api/2/issue/createmeta",
            params={"projectKeys": key, "expand": "projects.issuetypes.fields"},
            headers=_HEADERS,
            verify=_CA_BUNDLE,
            timeout=_TIMEOUT,
        )
        if cm.status_code == 200:
            projects = cm.json().get("projects", [])
            if projects:
                required_fields = {}
                for issuetype in projects[0].get("issuetypes", []):
                    for fname, fdata in issuetype.get("fields", {}).items():
                        if fdata.get("required") and fname.startswith("customfield_"):
                            # Store as empty placeholder — value must be set manually
                            required_fields[fname] = {}
                if required_fields:
                    cfg["required_custom"] = required_fields
                source = "jira_createmeta"
    except Exception as e:
        _logger.debug("createmeta not available for %s: %s", key, e)

    return cfg, source


def get_or_discover(key: str) -> dict:
    """
    Return config for project_key. If not in DB, discover from Jira and persist.
    Raises ValueError if the project does not exist in Jira.
    """
    key = key.upper()
    cached = _get_from_db(key)
    if cached:
        return cached

    _logger.info("Project %s not in DB — discovering from Jira", key)
    cfg, source = _discover_from_jira(key)
    _upsert(key, cfg, source)
    _logger.info("Project %s registered (source: %s)", key, source)
    return cfg


def seed(key: str, cfg: dict) -> None:
    """Insert known project config at startup if not already present."""
    existing = _get_from_db(key)
    if not existing:
        _upsert(key, cfg, "seed")


def list_projects() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM projects ORDER BY project_key"
        ).fetchall()
    return [
        {**_row_to_config(r), "project_key": r["project_key"], "discovered_at": r["discovered_at"]}
        for r in rows
    ]
