import os

import httpx

_SERVICE_URL = os.environ.get("SERVICE_URL", "http://service:8000")
_TIMEOUT = int(os.environ.get("MCP_SERVICE_TIMEOUT", "30"))


def _client(user: str) -> httpx.Client:
    return httpx.Client(
        base_url=_SERVICE_URL,
        headers={"x-user": user},
        timeout=_TIMEOUT,
    )


def _require(d: dict, *keys: str, endpoint: str) -> None:
    missing = [k for k in keys if k not in d]
    if missing:
        raise ValueError(f"{endpoint}: missing fields {missing} in response")


def create_issue(text: str, user: str) -> dict:
    with _client(user) as c:
        r = c.post("/issues", json={"text": text})
        r.raise_for_status()
        d = r.json()
        _require(d, "key", endpoint="POST /issues")
        return {"key": d["key"], "status": "created"}


def update_issue(key: str, text: str, user: str) -> dict:
    with _client(user) as c:
        r = c.patch(f"/issues/{key}", json={"text": text})
        r.raise_for_status()
        return {"key": key, "status": "updated"}


def get_issue(key: str, user: str) -> dict:
    with _client(user) as c:
        r = c.get(f"/issues/{key}/summary")
        r.raise_for_status()
        d = r.json()
        _require(d, "key", "summary", endpoint=f"GET /issues/{key}/summary")
        return {"key": d["key"], "summary": d["summary"]}


def assign_issue(key: str, text: str, user: str) -> dict:
    with _client(user) as c:
        r = c.post(f"/issues/{key}/assign", json={"text": text})
        r.raise_for_status()
        d = r.json()
        _require(d, "key", endpoint=f"POST /issues/{key}/assign")
        return {"key": d["key"], "status": "assigned", "assignee": d.get("assignee")}


def set_priority(key: str, text: str, user: str) -> dict:
    with _client(user) as c:
        r = c.post(f"/issues/{key}/priority", json={"text": text})
        r.raise_for_status()
        d = r.json()
        _require(d, "key", "priority", endpoint=f"POST /issues/{key}/priority")
        return {"key": d["key"], "status": "priority_updated", "priority": d["priority"]}


def add_comment(key: str, text: str, user: str) -> dict:
    with _client(user) as c:
        r = c.post(f"/issues/{key}/comments", json={"text": text})
        r.raise_for_status()
        d = r.json()
        _require(d, "key", "comment", endpoint=f"POST /issues/{key}/comments")
        return {"key": d["key"], "status": "comment_added"}


def link_issues(key: str, text: str, user: str) -> dict:
    with _client(user) as c:
        r = c.post(f"/issues/{key}/link", json={"text": text})
        r.raise_for_status()
        d = r.json()
        _require(d, "source_key", "target_key", endpoint=f"POST /issues/{key}/link")
        return {"source_key": d["source_key"], "target_key": d["target_key"], "status": "linked"}


def search_issues(query: str, user: str) -> dict:
    with _client(user) as c:
        r = c.post("/issues/search", json={"query": query})
        r.raise_for_status()
        d = r.json()
        _require(d, "total", "issues", endpoint="POST /issues/search")
        return {
            "total": d["total"],
            "issues": [
                {"key": i["key"], "summary": i["summary"]}
                for i in d["issues"]
            ],
        }
