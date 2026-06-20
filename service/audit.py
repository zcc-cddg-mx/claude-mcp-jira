import json
import os
from datetime import datetime, timezone
from pathlib import Path

_LOG_PATH = Path(os.environ.get("AUDIT_LOG_PATH", "audit.log"))


def log(
    *,
    user: str,
    action: str,
    input_text: str,
    claude_payload: dict | None = None,
    jira_key: str | None = None,
    status: str,
    error: str | None = None,
) -> None:
    entry = {
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
