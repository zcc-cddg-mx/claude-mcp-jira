import os
import time
from typing import Optional

import requests

from ..schemas import IssueResult, JiraIssuePayload, LogWorkPayload, SAZIssuePayload, TransitionPayload, UpdateIssuePayload

_JIRA_URL = os.environ.get("JIRA_URL", "").rstrip("/")
_JIRA_PAT = os.environ.get("JIRA_PAT", "")
_JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "")
_JIRA_SAZ_PROJECT_KEY = os.environ.get("JIRA_SAZ_PROJECT_KEY", "SAZ")
_CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE", True)
_TIMEOUT = int(os.environ.get("JIRA_TIMEOUT", "10"))

_HEADERS = {
    "Authorization": f"Bearer {_JIRA_PAT}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# ZNRX project requires customfield_25832 ("Línea de Servicio") on top-level issues.
# "BAU" (id 44461) is the standard value for development work.
_LINEA_SERVICIO_BAU = {"id": "44461"}

# ZNRX does not accept priority by name — must use ID.
# ZNRX only allows: Highest (1), High (2), Low (4). Any other value is omitted.
# "Bug" issuetype has additional workflow validations in ZNRX that block creation via API;
# fall back to "Task" and preserve intent in summary/description.
_PRIORITY_IDS = {
    "Highest": "1",
    "High": "2",
    "Low": "4",
}
_ISSUETYPE_FALLBACK = {"Bug": "Task", "Improvement": "Task"}


def _get(path: str) -> dict:
    r = requests.get(f"{_JIRA_URL}{path}", headers=_HEADERS, verify=_CA_BUNDLE, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict:
    r = requests.post(f"{_JIRA_URL}{path}", json=body, headers=_HEADERS, verify=_CA_BUNDLE, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def _put(path: str, body: dict) -> None:
    r = requests.put(f"{_JIRA_URL}{path}", json=body, headers=_HEADERS, verify=_CA_BUNDLE, timeout=_TIMEOUT)
    r.raise_for_status()


def _post_noret(path: str, body: dict) -> None:
    r = requests.post(f"{_JIRA_URL}{path}", json=body, headers=_HEADERS, verify=_CA_BUNDLE, timeout=_TIMEOUT)
    r.raise_for_status()


def create_issue(payload: JiraIssuePayload) -> str:
    issuetype = _ISSUETYPE_FALLBACK.get(payload.issueType, payload.issueType)
    priority_id = _PRIORITY_IDS.get(payload.priority)
    fields: dict = {
        "project": {"key": _JIRA_PROJECT_KEY},
        "summary": payload.summary,
        "description": payload.description,
        "issuetype": {"name": issuetype},
        "customfield_25832": _LINEA_SERVICIO_BAU,
    }
    if priority_id:
        fields["priority"] = {"id": priority_id}
    return _post("/rest/api/2/issue", {"fields": fields})["key"]


def get_issue(key: str) -> dict:
    return _get(f"/rest/api/2/issue/{key}")


def update_issue(key: str, payload: UpdateIssuePayload) -> None:
    fields: dict = {}
    if payload.summary is not None:
        fields["summary"] = payload.summary
    if payload.description is not None:
        fields["description"] = payload.description
    if payload.priority is not None:
        priority_id = _PRIORITY_IDS.get(payload.priority)
        if priority_id:
            fields["priority"] = {"id": priority_id}

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
        body["started"] = payload.started
    _post_noret(f"/rest/api/2/issue/{key}/worklog", body)


def clone_issue(source_key: str, source: dict, payload) -> str:
    f = source["fields"]
    issuetype = _ISSUETYPE_FALLBACK.get(f["issuetype"]["name"], f["issuetype"]["name"])
    parent = f.get("parent")

    summary = (payload.summary or f.get("summary", ""))[:100]
    description = payload.description or f.get("description", "") or ""

    fields: dict = {
        "project": {"key": _JIRA_PROJECT_KEY},
        "summary": summary,
        "description": description,
        "issuetype": {"name": issuetype},
    }

    if parent:
        # Subtasks: link to parent, no customfield_25832/priority (not on subtask screen)
        fields["parent"] = {"key": parent["key"]}
    else:
        # Top-level issues: Línea de Servicio required + priority
        fields["customfield_25832"] = _LINEA_SERVICIO_BAU
        priority_name = (f.get("priority") or {}).get("name", "Low")
        priority_id = _PRIORITY_IDS.get(priority_name)
        if priority_id:
            fields["priority"] = {"id": priority_id}

    new_key = _post("/rest/api/2/issue", {"fields": fields})["key"]

    # Link types: "Cloners" id=10001 — outward="clones", inward="is cloned by"
    # Only create link for top-level issues; subtasks are already tied to parent
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
    priority_id = _PRIORITY_IDS.get(priority)
    if priority_id:
        fields: dict = {"priority": {"id": priority_id}}
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
        _post_noret("/rest/api/2/issueLink", {
            "type": {"name": "Relates"},
            "outwardIssue": {"key": saz_key},
            "inwardIssue": {"key": znrx_key},
        })
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
