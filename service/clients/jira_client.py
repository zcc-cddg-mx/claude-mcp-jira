import os

import requests

from ..schemas import IssueResult, JiraIssuePayload, UpdateIssuePayload

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
    body = {
        "fields": {
            "project": {"key": _JIRA_PROJECT_KEY},
            "summary": payload.summary,
            "description": payload.description,
            "issuetype": {"name": payload.issueType},
            "priority": {"name": payload.priority},
        }
    }
    return _post("/rest/api/2/issue", body)["key"]


def get_issue(key: str) -> dict:
    return _get(f"/rest/api/2/issue/{key}")


def update_issue(key: str, payload: UpdateIssuePayload) -> None:
    fields: dict = {}
    if payload.summary is not None:
        fields["summary"] = payload.summary
    if payload.description is not None:
        fields["description"] = payload.description
    if payload.priority is not None:
        fields["priority"] = {"name": payload.priority}

    if fields:
        _put(f"/rest/api/2/issue/{key}", {"fields": fields})

    if payload.comment:
        _post_noret(
            f"/rest/api/2/issue/{key}/comment",
            {"body": payload.comment},
        )


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
