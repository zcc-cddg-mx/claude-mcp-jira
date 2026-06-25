"""
SQLite-backed store for WorkflowExecution records.

Each execution tracks the progress of a multi-step orchestration workflow
(e.g. CreateFeaturePR: preview → git → PR → CI → link Jira).

The service layer only persists state here; the MCP tool drives execution.
"""

import json
import logging
import os
import sqlite3
import threading
import uuid
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


def init_workflow_db() -> None:
    with _lock, _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS workflow_executions (
                execution_id   TEXT PRIMARY KEY,
                workflow_type  TEXT NOT NULL,
                issue_key      TEXT NOT NULL,
                status         TEXT NOT NULL,
                steps_json     TEXT NOT NULL DEFAULT '[]',
                result_json    TEXT,
                error          TEXT,
                created_at     TEXT NOT NULL,
                updated_at     TEXT NOT NULL,
                user           TEXT NOT NULL
            )
        """)
        c.commit()


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "execution_id": row["execution_id"],
        "workflow_type": row["workflow_type"],
        "issue_key": row["issue_key"],
        "status": row["status"],
        "steps": json.loads(row["steps_json"]),
        "result": json.loads(row["result_json"]) if row["result_json"] else None,
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "user": row["user"],
    }


def create_execution(workflow_type: str, issue_key: str, user: str) -> dict:
    execution_id = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc).isoformat()
    with _lock, _conn() as c:
        c.execute("""
            INSERT INTO workflow_executions
                (execution_id, workflow_type, issue_key, status, steps_json,
                 result_json, error, created_at, updated_at, user)
            VALUES (?, ?, ?, 'pending', '[]', NULL, NULL, ?, ?, ?)
        """, (execution_id, workflow_type, issue_key.upper(), now, now, user))
        c.commit()
    _logger.info("workflow execution created: %s (%s %s)", execution_id, workflow_type, issue_key)
    return get_execution(execution_id)


def update_execution(
    execution_id: str,
    status: Optional[str] = None,
    steps: Optional[list] = None,
    result: Optional[dict] = None,
    error: Optional[str] = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    sets = ["updated_at = ?"]
    params: list = [now]
    if status is not None:
        sets.append("status = ?")
        params.append(status)
    if steps is not None:
        sets.append("steps_json = ?")
        params.append(json.dumps(steps))
    if result is not None:
        sets.append("result_json = ?")
        params.append(json.dumps(result))
    if error is not None:
        sets.append("error = ?")
        params.append(error)
    params.append(execution_id)
    with _lock, _conn() as c:
        c.execute(
            f"UPDATE workflow_executions SET {', '.join(sets)} WHERE execution_id = ?",
            params,
        )
        c.commit()


def get_execution(execution_id: str) -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM workflow_executions WHERE execution_id = ?",
            (execution_id,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_executions(
    issue_key: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    query = "SELECT * FROM workflow_executions"
    clauses: list[str] = []
    params: list = []
    if issue_key:
        clauses.append("issue_key = ?")
        params.append(issue_key.upper())
    if status:
        clauses.append("status = ?")
        params.append(status)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with _conn() as c:
        rows = c.execute(query, params).fetchall()
    return [_row_to_dict(r) for r in rows]
