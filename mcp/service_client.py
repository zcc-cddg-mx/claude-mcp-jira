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


def create_issue(text: str, user: str) -> dict:
    with _client(user) as c:
        r = c.post("/issues", json={"text": text})
        r.raise_for_status()
        d = r.json()
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
        return {"key": d["key"], "summary": d["summary"]}


def search_issues(query: str, user: str) -> dict:
    with _client(user) as c:
        r = c.post("/issues/search", json={"query": query})
        r.raise_for_status()
        d = r.json()
        return {
            "total": d["total"],
            "issues": [
                {"key": i["key"], "summary": i["summary"]}
                for i in d["issues"]
            ],
        }
