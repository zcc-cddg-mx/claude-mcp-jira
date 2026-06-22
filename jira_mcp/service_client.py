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


def create_issue(text: str, user: str, project: str = None) -> dict:
    body = {"text": text}
    if project:
        body["project"] = project
    with _client(user) as c:
        r = c.post("/issues", json=body)
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


def create_saz(text: str, znrx_key, user: str) -> dict:
    body = {"text": text}
    if znrx_key:
        body["znrx_key"] = znrx_key
    with _client(user) as c:
        r = c.post("/issues/saz", json=body)
        r.raise_for_status()
        d = r.json()
        _require(d, "saz_key", endpoint="POST /issues/saz")
        result = {"saz_key": d["saz_key"], "status": d.get("status", "created")}
        if d.get("znrx_key"):
            result["znrx_key"] = d["znrx_key"]
        return result


def sync_git_worklogs(repo_path: str = None, user: str = "anonymous", since_days: int = 1, dry_run: bool = True, author: str = None, repo_name: str = None) -> dict:
    body: dict = {"since_days": since_days, "dry_run": dry_run}
    if repo_path:
        body["repo_path"] = repo_path
    if repo_name:
        body["repo_name"] = repo_name
    if author:
        body["author"] = author
    with _client(user) as c:
        r = c.post("/git/sync", json=body)
        r.raise_for_status()
        d = r.json()
        _require(d, "sessions", "total_commits", endpoint="POST /git/sync")
        return {
            "repo": d["repo_path"],
            "branch": d.get("branch"),
            "total_commits": d["total_commits"],
            "dry_run": d["dry_run"],
            "sessions": [
                {
                    "issue_key": s["issue_key"],
                    "estimated_hours": s["estimated_hours"],
                    "confidence": s["confidence"],
                    "commits": s["commit_count"],
                    "worklog_registered": s["worklog_registered"],
                }
                for s in d["sessions"]
            ],
            "worklogs_registered": d["worklogs_registered"],
        }


def register_git_repo(
    name: str,
    repo_path: str,
    user: str,
    jira_project: str = None,
    default_issue_key: str = None,
    is_default: bool = False,
) -> dict:
    body: dict = {"name": name, "repo_path": repo_path, "is_default": is_default}
    if jira_project:
        body["jira_project"] = jira_project
    if default_issue_key:
        body["default_issue_key"] = default_issue_key
    with _client(user) as c:
        r = c.post("/git/repos", json=body)
        r.raise_for_status()
        return r.json()


def list_git_repos(user: str) -> dict:
    with _client(user) as c:
        r = c.get("/git/repos")
        r.raise_for_status()
        return r.json()


def search_issues(query: str, user: str, project: str = None) -> dict:
    body = {"query": query}
    if project:
        body["project"] = project
    with _client(user) as c:
        r = c.post("/issues/search", json=body)
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
