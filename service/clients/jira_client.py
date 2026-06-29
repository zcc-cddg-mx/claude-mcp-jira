import os
import time
from contextvars import ContextVar
from typing import Optional

import requests

from ..schemas import IssueResult, JiraIssuePayload, LogWorkPayload, SAZIssuePayload, TransitionPayload, UpdateIssuePayload
from .project_config import get_config, resolve_project

_JIRA_URL = os.environ.get("JIRA_URL", "").rstrip("/")
_JIRA_PAT = os.environ.get("JIRA_PAT", "")
_JIRA_SAZ_PROJECT_KEY = os.environ.get("JIRA_SAZ_PROJECT_KEY", "SAZ")
_CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE", True)
_TIMEOUT = int(os.environ.get("JIRA_TIMEOUT", "10"))

# Per-request PAT override — set by JiraAuthMiddleware when X-Jira-Token header is present
_request_pat: ContextVar[str | None] = ContextVar("request_pat", default=None)


def _get_headers() -> dict:
    pat = _request_pat.get() or _JIRA_PAT
    return {
        "Authorization": f"Bearer {pat}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _get(path: str) -> dict:
    r = requests.get(f"{_JIRA_URL}{path}", headers=_get_headers(), verify=_CA_BUNDLE, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict:
    r = requests.post(f"{_JIRA_URL}{path}", json=body, headers=_get_headers(), verify=_CA_BUNDLE, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def _put(path: str, body: dict) -> None:
    r = requests.put(f"{_JIRA_URL}{path}", json=body, headers=_get_headers(), verify=_CA_BUNDLE, timeout=_TIMEOUT)
    r.raise_for_status()


def _post_noret(path: str, body: dict) -> None:
    r = requests.post(f"{_JIRA_URL}{path}", json=body, headers=_get_headers(), verify=_CA_BUNDLE, timeout=_TIMEOUT)
    r.raise_for_status()


def create_issue(payload: JiraIssuePayload, project_key: Optional[str] = None) -> str:
    key = resolve_project(project_key)
    cfg = get_config(key)
    issuetype = cfg["issuetype_fallback"].get(payload.issueType, payload.issueType)
    fields: dict = {
        "project": {"key": key},
        "summary": payload.summary,
        "description": payload.description,
        "issuetype": {"name": issuetype},
    }
    fields.update(cfg["required_custom"])
    if cfg["priority_format"] == "id":
        priority_id = cfg["priority_ids"].get(payload.priority)
        if priority_id:
            fields["priority"] = {"id": priority_id}
    else:
        fields["priority"] = {"name": payload.priority}
    return _post("/rest/api/2/issue", {"fields": fields})["key"]


def get_issue(key: str) -> dict:
    return _get(f"/rest/api/2/issue/{key}")


def _project_from_key(issue_key: str) -> str:
    return issue_key.split("-")[0].upper()


def update_issue(key: str, payload: UpdateIssuePayload) -> None:
    cfg = get_config(_project_from_key(key))
    fields: dict = {}
    if payload.summary is not None:
        fields["summary"] = payload.summary
    if payload.description is not None:
        fields["description"] = payload.description
    if payload.priority is not None:
        if cfg["priority_format"] == "id":
            priority_id = cfg["priority_ids"].get(payload.priority)
            if priority_id:
                fields["priority"] = {"id": priority_id}
        else:
            fields["priority"] = {"name": payload.priority}

    if fields:
        _put(f"/rest/api/2/issue/{key}", {"fields": fields})

    if payload.comment:
        _post_noret(
            f"/rest/api/2/issue/{key}/comment",
            {"body": payload.comment},
        )


def get_transitions(key: str) -> list[dict]:
    data = _get(f"/rest/api/2/issue/{key}/transitions")
    return [{"id": t["id"], "name": t["name"]} for t in data.get("transitions", [])]


def transition_issue(key: str, payload: TransitionPayload) -> str:
    _post_noret(
        f"/rest/api/2/issue/{key}/transitions",
        {"transition": {"id": payload.transition_id}},
    )
    issue = _get(f"/rest/api/2/issue/{key}?fields=status")
    return issue["fields"]["status"]["name"]


def log_work(key: str, payload: LogWorkPayload) -> None:
    body: dict = {"timeSpentSeconds": payload.time_spent_seconds}
    if payload.comment:
        body["comment"] = payload.comment
    if payload.started:
        # Claude returns midnight UTC (T00:00:00.000+0000) when only a date is given.
        # Jira stores UTC and displays in server TZ (Europe/Madrid UTC+2), which can
        # shift the date. Normalize to 09:00 Ecuador time (-0500) so the worklog always
        # falls on the intended calendar day in any server timezone.
        started = payload.started
        if "T00:00:00.000+0000" in started:
            started = started.replace("T00:00:00.000+0000", "T09:00:00.000-0500")
        body["started"] = started
    _post_noret(f"/rest/api/2/issue/{key}/worklog", body)


def clone_issue(source_key: str, source: dict, payload) -> str:
    project = _project_from_key(source_key)
    cfg = get_config(project)
    f = source["fields"]

    issuetype_name = f["issuetype"]["name"]
    issuetype = cfg["issuetype_fallback"].get(issuetype_name, issuetype_name)
    parent = f.get("parent")

    summary = (payload.summary or f.get("summary", ""))[:100]
    description = payload.description or f.get("description", "") or ""

    fields: dict = {
        "project": {"key": project},
        "summary": summary,
        "description": description,
        "issuetype": {"name": issuetype},
    }

    if parent:
        # Subtasks: link to parent, no required_custom/priority (not on subtask screen)
        fields["parent"] = {"key": parent["key"]}
    else:
        # Top-level: inject required custom fields (e.g. customfield_25832 in ZNRX)
        for field_key, field_val in cfg["required_custom"].items():
            fields[field_key] = field_val

        priority_name = (f.get("priority") or {}).get("name", "Low")
        if cfg["priority_format"] == "id":
            priority_id = cfg["priority_ids"].get(priority_name)
            if priority_id:
                fields["priority"] = {"id": priority_id}
        else:
            fields["priority"] = {"name": priority_name}

    new_key = _post("/rest/api/2/issue", {"fields": fields})["key"]

    # Only link top-level issues; subtasks are already tied to parent
    if not parent:
        _post_noret("/rest/api/2/issueLink", {
            "type": {"name": "Cloners"},
            "outwardIssue": {"key": source_key},
            "inwardIssue": {"key": new_key},
        })

    return new_key


_link_types_cache: list[dict] = []
_link_types_cache_ts: float = 0.0
_LINK_TYPES_TTL = 3600


def get_link_types() -> list[dict]:
    global _link_types_cache, _link_types_cache_ts
    if _link_types_cache and (time.time() - _link_types_cache_ts) < _LINK_TYPES_TTL:
        return _link_types_cache
    data = _get("/rest/api/2/issueLinkType")
    _link_types_cache = [
        {"id": t["id"], "name": t["name"], "outward": t["outward"], "inward": t["inward"]}
        for t in data.get("issueLinkTypes", [])
    ]
    _link_types_cache_ts = time.time()
    return _link_types_cache


def link_issue(source_key: str, target_key: str, link_type_name: str, source_is_outward: bool) -> None:
    if source_is_outward:
        body = {
            "type": {"name": link_type_name},
            "outwardIssue": {"key": source_key},
            "inwardIssue": {"key": target_key},
        }
    else:
        body = {
            "type": {"name": link_type_name},
            "outwardIssue": {"key": target_key},
            "inwardIssue": {"key": source_key},
        }
    _post_noret("/rest/api/2/issueLink", body)


def assign_issue(key: str, assignee: Optional[str]) -> None:
    # Jira Server uses PUT /rest/api/2/issue/{key}/assignee
    # Pass {"name": username} or {"name": None} to unassign
    body = {"name": assignee}
    _put(f"/rest/api/2/issue/{key}/assignee", body)


def set_priority(key: str, priority: str) -> None:
    cfg = get_config(_project_from_key(key))
    if cfg["priority_format"] == "id":
        priority_id = cfg["priority_ids"].get(priority)
        fields: dict = {"priority": {"id": priority_id}} if priority_id else {"priority": {"name": priority}}
    else:
        fields = {"priority": {"name": priority}}
    _put(f"/rest/api/2/issue/{key}", {"fields": fields})


def add_comment(key: str, comment: str) -> None:
    _post_noret(f"/rest/api/2/issue/{key}/comment", {"body": comment})


def get_labels(key: str) -> list[str]:
    issue = _get(f"/rest/api/2/issue/{key}?fields=labels")
    return issue["fields"].get("labels", [])


def update_labels(key: str, labels: list[str]) -> None:
    _put(f"/rest/api/2/issue/{key}", {"fields": {"labels": labels}})


def create_saz_issue(payload: SAZIssuePayload, znrx_key: Optional[str] = None) -> str:
    fields: dict = {
        "project": {"key": _JIRA_SAZ_PROJECT_KEY},
        "summary": payload.summary,
        "description": payload.description,
        "issuetype": {"name": payload.issue_type},
    }
    saz_key = _post("/rest/api/2/issue", {"fields": fields})["key"]
    if znrx_key:
        try:
            _post_noret("/rest/api/2/issueLink", {
                "type": {"name": "Relates"},
                "outwardIssue": {"key": saz_key},
                "inwardIssue": {"key": znrx_key},
            })
        except Exception:
            pass  # SAZ created; link is best-effort
    return saz_key


def search_issues(jql: str, max_results: int) -> list[IssueResult]:
    body = {
        "jql": jql,
        "maxResults": max_results,
        "fields": ["summary", "status", "priority", "assignee"],
    }
    data = _post("/rest/api/2/search", body)
    results = []
    for item in data.get("issues", []):
        f = item["fields"]
        results.append(IssueResult(
            key=item["key"],
            summary=f.get("summary", ""),
            status=f.get("status", {}).get("name", ""),
            priority=f.get("priority", {}).get("name", ""),
            assignee=f.get("assignee", {}).get("displayName") if f.get("assignee") else None,
        ))
    return results
