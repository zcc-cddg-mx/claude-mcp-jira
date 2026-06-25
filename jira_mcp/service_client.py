import os
from typing import Optional

import httpx

_SERVICE_URL = os.environ.get("SERVICE_URL", "http://service:8000")
_TIMEOUT = int(os.environ.get("MCP_SERVICE_TIMEOUT", "30"))
_CODE_AGENT_URL = os.environ.get("CODE_AGENT_URL", "http://code-agent-mcp:5001")
_CODE_AGENT_TOKEN = os.environ.get("CODE_AGENT_TOKEN", "")
_CODE_AGENT_TIMEOUT = int(os.environ.get("CODE_AGENT_TIMEOUT", "30"))


def _agent_client() -> httpx.Client:
    return httpx.Client(
        base_url=_CODE_AGENT_URL,
        headers={"X-Agent-Token": _CODE_AGENT_TOKEN},
        timeout=_CODE_AGENT_TIMEOUT,
    )


def _client(user: str, jira_token: str | None = None) -> httpx.Client:
    headers: dict = {"x-user": user}
    if jira_token:
        headers["X-Jira-Token"] = jira_token
    return httpx.Client(
        base_url=_SERVICE_URL,
        headers=headers,
        timeout=_TIMEOUT,
    )


def _require(d: dict, *keys: str, endpoint: str) -> None:
    missing = [k for k in keys if k not in d]
    if missing:
        raise ValueError(f"{endpoint}: missing fields {missing} in response")


def create_issue(text: str, user: str, project: str = None, jira_token: str = None) -> dict:
    body = {"text": text}
    if project:
        body["project"] = project
    with _client(user, jira_token) as c:
        r = c.post("/issues", json=body)
        r.raise_for_status()
        d = r.json()
        _require(d, "key", endpoint="POST /issues")
        return {"key": d["key"], "status": "created"}


def update_issue(key: str, text: str, user: str, jira_token: str = None) -> dict:
    with _client(user, jira_token) as c:
        r = c.patch(f"/issues/{key}", json={"text": text})
        r.raise_for_status()
        return {"key": key, "status": "updated"}


def get_issue(key: str, user: str, jira_token: str = None) -> dict:
    with _client(user, jira_token) as c:
        r = c.get(f"/issues/{key}/summary")
        r.raise_for_status()
        d = r.json()
        _require(d, "key", "summary", endpoint=f"GET /issues/{key}/summary")
        return {"key": d["key"], "summary": d["summary"]}


def assign_issue(key: str, text: str, user: str, jira_token: str = None) -> dict:
    with _client(user, jira_token) as c:
        r = c.post(f"/issues/{key}/assign", json={"text": text})
        r.raise_for_status()
        d = r.json()
        _require(d, "key", endpoint=f"POST /issues/{key}/assign")
        return {"key": d["key"], "status": "assigned", "assignee": d.get("assignee")}


def set_priority(key: str, text: str, user: str, jira_token: str = None) -> dict:
    with _client(user, jira_token) as c:
        r = c.post(f"/issues/{key}/priority", json={"text": text})
        r.raise_for_status()
        d = r.json()
        _require(d, "key", "priority", endpoint=f"POST /issues/{key}/priority")
        return {"key": d["key"], "status": "priority_updated", "priority": d["priority"]}


def add_comment(key: str, text: str, user: str, jira_token: str = None) -> dict:
    with _client(user, jira_token) as c:
        r = c.post(f"/issues/{key}/comments", json={"text": text})
        r.raise_for_status()
        d = r.json()
        _require(d, "key", "comment", endpoint=f"POST /issues/{key}/comments")
        return {"key": d["key"], "status": "comment_added"}


def link_issues(key: str, text: str, user: str, jira_token: str = None) -> dict:
    with _client(user, jira_token) as c:
        r = c.post(f"/issues/{key}/link", json={"text": text})
        r.raise_for_status()
        d = r.json()
        _require(d, "source_key", "target_key", endpoint=f"POST /issues/{key}/link")
        return {"source_key": d["source_key"], "target_key": d["target_key"], "status": "linked"}


def create_saz(text: str, znrx_key, user: str, jira_token: str = None) -> dict:
    body = {"text": text}
    if znrx_key:
        body["znrx_key"] = znrx_key
    with _client(user, jira_token) as c:
        r = c.post("/issues/saz", json=body)
        r.raise_for_status()
        d = r.json()
        _require(d, "saz_key", endpoint="POST /issues/saz")
        result = {"saz_key": d["saz_key"], "status": d.get("status", "created")}
        if d.get("znrx_key"):
            result["znrx_key"] = d["znrx_key"]
        return result


def sync_git_worklogs(repo_path: str = None, user: str = "anonymous", since_days: int = 1, dry_run: bool = True, author: str = None, repo_name: str = None, jira_token: str = None) -> dict:
    body: dict = {"since_days": since_days, "dry_run": dry_run}
    if repo_path:
        body["repo_path"] = repo_path
    if repo_name:
        body["repo_name"] = repo_name
    if author:
        body["author"] = author
    with _client(user, jira_token) as c:
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


def search_issues(query: str, user: str, project: str = None, jira_token: str = None) -> dict:
    body = {"query": query}
    if project:
        body["project"] = project
    with _client(user, jira_token) as c:
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


# ─── Code Agent MCP ──────────────────────────────────────────────────────────

def run_code_agent(
    repo: str,
    branch: str,
    files: list,
    ticket: str,
    commit_message: str,
    base_branch: Optional[str] = None,
    target: Optional[str] = None,
) -> dict:
    body: dict = {
        "repo": repo,
        "branch": branch,
        "files": files,
        "ticket": ticket,
        "commit_message": commit_message,
    }
    if base_branch:
        body["base_branch"] = base_branch
    if target:
        body["target"] = target
    with _agent_client() as c:
        r = c.post("/run", json=body)
        r.raise_for_status()
        d = r.json()
        return {"task_id": d["task_id"], "status": d.get("status", "queued")}


def get_code_agent_status(task_id: str) -> dict:
    with _agent_client() as c:
        r = c.get(f"/status/{task_id}")
        r.raise_for_status()
        d = r.json()
        result: dict = {
            "task_id": d["task_id"],
            "status": d["status"],
            "ticket": d.get("ticket"),
        }
        for field in ("branch", "aux_branch", "commit_id", "error"):
            if d.get(field):
                result[field] = d[field]
        return result


def create_azure_pull_request(
    repo: str,
    repo_path: str,
    branch: str,
    files: list,
    target: str,
    ticket: str,
    title: str,
    description: str = "",
) -> dict:
    body = {
        "repo": repo,
        "repo_path": repo_path,
        "branch": branch,
        "files": files,
        "target": target,
        "ticket": ticket,
        "title": title,
        "description": description,
    }
    with _agent_client() as c:
        r = c.post("/azure/prepare-and-pr", json=body)
        r.raise_for_status()
        d = r.json()
        pr = d.get("pr") or {}
        return {
            "aux_branch":  d.get("aux_branch"),
            "action":      d.get("action"),
            "pr_id":       pr.get("pr_id"),
            "pr_url":      pr.get("pr_url"),
            "base_branch": d.get("base_branch"),
            "real_target": d.get("real_target"),
        }


def get_pull_request_status(pr_id: int, repo: str) -> dict:
    with _agent_client() as c:
        r = c.get(f"/azure/pull-requests/{pr_id}", params={"repo": repo})
        r.raise_for_status()
        d = r.json()
        return {
            "pr_id": d["pr_id"],
            "status": d["status"],
            "build_status": d["build_status"],
            "pr_url": d.get("pr_url"),
        }


def create_deployment_saz(
    task: str,
    repo: str,
    target: str,
    branch: str,
    base_branch: str,
    pr_id: int | str,
    pr_url: str,
    user: str,
    znrx_key: Optional[str] = None,
    project_label: str = "OV",
    jira_token: Optional[str] = None,
) -> dict:
    body: dict = {
        "task": task,
        "repo": repo,
        "target": target,
        "branch": branch,
        "base_branch": base_branch,
        "pr_id": pr_id,
        "pr_url": pr_url,
        "project_label": project_label,
    }
    if znrx_key:
        body["znrx_key"] = znrx_key
    with _client(user, jira_token) as c:
        r = c.post("/issues/saz/deployment", json=body)
        r.raise_for_status()
        return r.json()


def preview_code_agent(
    repo: str,
    repo_path: str,
    target: str = "developer",
    files: Optional[list] = None,
) -> dict:
    body: dict = {"repo": repo, "repo_path": repo_path, "target": target, "files": files or []}
    with _agent_client() as c:
        r = c.post("/azure/prepare-and-pr/preview", json=body)
        r.raise_for_status()
        d = r.json()
        return {
            "base_branch": d.get("base_branch"),
            "files_detected": d.get("files_detected", []),
        }


# ─── Workflow Orchestrator (Fase 10) ─────────────────────────────────────────

def create_workflow(
    issue_key: str,
    repo: str,
    repo_path: str,
    target: str,
    commit_message: str,
    files: list,
    user: str,
    jira_token: Optional[str] = None,
) -> dict:
    body = {
        "issue_key": issue_key,
        "repo": repo,
        "repo_path": repo_path,
        "target": target,
        "commit_message": commit_message,
        "files": files,
    }
    with _client(user, jira_token) as c:
        r = c.post("/workflows/create-feature-pr", json=body)
        r.raise_for_status()
        return r.json()


def get_workflow_status_by_id(execution_id: str, user: str) -> dict:
    with _client(user) as c:
        r = c.get(f"/workflows/{execution_id}")
        r.raise_for_status()
        return r.json()


def update_workflow(
    execution_id: str,
    user: str,
    status: Optional[str] = None,
    steps: Optional[list] = None,
    result: Optional[dict] = None,
    error: Optional[str] = None,
) -> dict:
    body: dict = {}
    if status is not None:
        body["status"] = status
    if steps is not None:
        body["steps"] = steps
    if result is not None:
        body["result"] = result
    if error is not None:
        body["error"] = error
    with _client(user) as c:
        r = c.patch(f"/workflows/{execution_id}", json=body)
        r.raise_for_status()
        return r.json()


# ─── Deployment SAZ workflow helpers ─────────────────────────────────────────

def get_repo_by_alias(alias: str, user: str) -> dict:
    with _client(user) as c:
        r = c.get(f"/git/repos/{alias}")
        r.raise_for_status()
        d = r.json()
        _require(d, "name", "repo_path", endpoint=f"GET /git/repos/{alias}")
        return d


def set_repo_branch_map(repo_name: str, branch_map: dict) -> dict:
    """Set per-repo target→branch mapping in code-agent-mcp registry.
    Calls PATCH /repos/<name>/branch-map on code-agent-mcp.
    branch_map example: {"developer": "developer", "test": "test", "prod": "develop"}
    """
    with _agent_client() as c:
        r = c.patch(f"/repos/{repo_name}/branch-map", json=branch_map)
        r.raise_for_status()
        return r.json()
