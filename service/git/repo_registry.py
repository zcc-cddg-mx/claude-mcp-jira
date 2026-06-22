"""
SQLite-backed registry of local Git repositories.

Each entry maps a short name/alias to:
  - repo_path        — absolute path to the local clone
  - origin           — remote URL (informational; extracted automatically if not given)
  - jira_project     — Jira project key to use when no issue key is found in commits
  - default_issue_key — specific ticket to log work against when no key found (overrides jira_project)
  - is_default       — only one repo can be default at a time

Schema:
  name               TEXT PRIMARY KEY
  repo_path          TEXT NOT NULL
  origin             TEXT
  jira_project       TEXT
  default_issue_key  TEXT
  is_default         INTEGER NOT NULL DEFAULT 0
  created_at         TEXT NOT NULL
"""

import logging
import os
import re
import sqlite3
import subprocess
import threading
from datetime import datetime, timezone
from typing import Optional

_logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "projects.db")
_DB_PATH = os.environ.get("PROJECT_DB_PATH", _DEFAULT_DB_PATH)

_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init_repo_registry() -> None:
    with _lock, _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS git_repos (
                name               TEXT PRIMARY KEY,
                repo_path          TEXT NOT NULL,
                origin             TEXT,
                jira_project       TEXT,
                default_issue_key  TEXT,
                is_default         INTEGER NOT NULL DEFAULT 0,
                created_at         TEXT NOT NULL
            )
        """)
        c.commit()


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "name": row["name"],
        "repo_path": row["repo_path"],
        "origin": row["origin"],
        "jira_project": row["jira_project"],
        "default_issue_key": row["default_issue_key"],
        "is_default": bool(row["is_default"]),
        "created_at": row["created_at"],
    }


def register_repo(
    name: str,
    repo_path: str,
    jira_project: Optional[str] = None,
    default_issue_key: Optional[str] = None,
    is_default: bool = False,
    origin: Optional[str] = None,
) -> dict:
    """
    Register or update a repo entry. If is_default=True, clears is_default on all others.
    Auto-detects origin from git remote if not provided.
    """
    if not origin:
        origin = _detect_origin(repo_path)

    now = datetime.now(timezone.utc).isoformat()

    with _lock, _conn() as c:
        if is_default:
            c.execute("UPDATE git_repos SET is_default = 0")
        c.execute("""
            INSERT INTO git_repos
                (name, repo_path, origin, jira_project, default_issue_key, is_default, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                repo_path          = excluded.repo_path,
                origin             = excluded.origin,
                jira_project       = excluded.jira_project,
                default_issue_key  = excluded.default_issue_key,
                is_default         = excluded.is_default,
                created_at         = excluded.created_at
        """, (name, repo_path, origin, jira_project, default_issue_key, int(is_default), now))
        c.commit()

    return get_repo(name)


def get_repo(name: str) -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM git_repos WHERE name = ?", (name,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_default_repo() -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM git_repos WHERE is_default = 1 LIMIT 1"
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_repos() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM git_repos ORDER BY is_default DESC, name"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def delete_repo(name: str) -> bool:
    with _lock, _conn() as c:
        cur = c.execute("DELETE FROM git_repos WHERE name = ?", (name,))
        c.commit()
    return cur.rowcount > 0


def resolve_repo(name_or_path: Optional[str]) -> Optional[dict]:
    """
    Resolve a repo by name, path, or fallback to the default repo.
    Returns None if nothing matches.
    """
    if not name_or_path:
        return get_default_repo()

    # Try by name first
    by_name = get_repo(name_or_path)
    if by_name:
        return by_name

    # Try matching by repo_path
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM git_repos WHERE repo_path = ?", (name_or_path,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def _detect_origin(repo_path: str) -> Optional[str]:
    try:
        r = subprocess.run(
            ["git", "-C", repo_path, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        url = r.stdout.strip()
        return url if url else None
    except Exception:
        return None


_KEY_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")


def infer_name_from_path(repo_path: str) -> str:
    """Return a sensible default name from a repo path (last directory component)."""
    return os.path.basename(repo_path.rstrip("/"))
