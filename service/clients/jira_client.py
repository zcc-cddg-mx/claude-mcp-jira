import os

import requests

from ..schemas import IssueResult, JiraIssuePayload, LogWorkPayload, TransitionPayload, UpdateIssuePayload

_JIRA_URL = os.environ.get("JIRA_URL", "").rstrip("/")
_JIRA_PAT = os.environ.get("JIRA_PAT", "")
_JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "")
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
