import os
from typing import Optional

import httpx

_CODE_AGENT_URL = os.environ.get("CODE_AGENT_URL", "http://code-agent-mcp:5001")
_CODE_AGENT_TOKEN = os.environ.get("CODE_AGENT_TOKEN", "")
_TIMEOUT = int(os.environ.get("CODE_AGENT_TIMEOUT", "30"))


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=_CODE_AGENT_URL,
        headers={"X-Agent-Token": _CODE_AGENT_TOKEN},
        timeout=_TIMEOUT,
    )


def run_task(
    repo: str,
    branch: str,
    files: list[str],
    ticket: str,
    commit_message: str,
    base_branch: Optional[str] = None,
    target: Optional[str] = None,
    callback_url: Optional[str] = None,
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
    if callback_url:
        body["callback_url"] = callback_url
    with _client() as c:
        r = c.post("/run", json=body)
        r.raise_for_status()
        d = r.json()
        return {"task_id": d["task_id"], "status": d.get("status", "queued")}


def get_task_status(task_id: str) -> dict:
    with _client() as c:
        r = c.get(f"/status/{task_id}")
        r.raise_for_status()
        d = r.json()
        result: dict = {
            "task_id": d["task_id"],
            "status": d["status"],
            "ticket": d.get("ticket"),
        }
        if d.get("branch"):
            result["branch"] = d["branch"]
        if d.get("aux_branch"):
            result["aux_branch"] = d["aux_branch"]
        if d.get("commit_id"):
            result["commit_id"] = d["commit_id"]
        if d.get("error"):
            result["error"] = d["error"]
        return result


def prepare_and_pr(
    repo: str,
    branch: str,
    target: str,
    ticket: str,
    title: str,
    repo_path: Optional[str] = None,
    files: Optional[list[str]] = None,
    description: str = "",
) -> dict:
    body: dict = {
        "repo": repo,
        "branch": branch,
        "target": target,
        "ticket": ticket,
        "title": title,
        "description": description,
    }
    if repo_path:
        body["repo_path"] = repo_path
    if files:
        body["files"] = files
    with _client() as c:
        r = c.post("/azure/prepare-and-pr", json=body)
        r.raise_for_status()
        d = r.json()
        pr = d.get("pr") or {}
        return {
            "aux_branch": d.get("aux_branch"),
            "action": d.get("action"),
            "pr_id": pr.get("pr_id"),
            "pr_url": pr.get("pr_url"),
        }


def get_pr_status(pr_id: int, repo: str) -> dict:
    with _client() as c:
        r = c.get(f"/azure/pull-requests/{pr_id}", params={"repo": repo})
        r.raise_for_status()
        d = r.json()
        return {
            "pr_id": d["pr_id"],
            "status": d["status"],
            "build_status": d["build_status"],
            "pr_url": d.get("pr_url"),
        }
