import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

_LOG_PATH = Path(os.environ.get("AUDIT_LOG_PATH", "audit.log"))


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
        "status": status,
        "error": error,
    }
    with _LOG_PATH.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
