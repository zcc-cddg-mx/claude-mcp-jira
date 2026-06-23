import json
import logging
import logging.handlers
import os
import uuid
from datetime import datetime, timezone

from .clients.jira_client import _request_pat

_LOG_PATH = os.environ.get("AUDIT_LOG_PATH", "audit.log")
_MAX_BYTES = int(os.environ.get("AUDIT_LOG_MAX_BYTES", str(10 * 1024 * 1024)))  # 10 MB
_BACKUP_COUNT = int(os.environ.get("AUDIT_LOG_BACKUP_COUNT", "5"))

_handler = logging.handlers.RotatingFileHandler(
    _LOG_PATH, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
)
_audit_logger = logging.getLogger("jira_mcp.audit_file")
_audit_logger.addHandler(_handler)
_audit_logger.setLevel(logging.INFO)
_audit_logger.propagate = False


def new_request_id() -> str:
    return str(uuid.uuid4())


def log(
    *,
    request_id: str,
    user: str,
    action: str,
    input_text: str,
    claude_payload: dict | None = None,
    jira_key: str | None = None,
    status: str,
    error: str | None = None,
) -> None:
    entry = {
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": user,
        "action": action,
        "input": input_text,
        "claude_payload": claude_payload,
        "jira_key": jira_key,
        "pat_source": "header" if _request_pat.get() else "env",
        "status": status,
        "error": error,
    }
    _audit_logger.info(json.dumps(entry, ensure_ascii=False))
