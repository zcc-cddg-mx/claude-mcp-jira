import os

import requests

from ..schemas import JiraIssuePayload

_JIRA_URL = os.environ.get("JIRA_URL", "").rstrip("/")
_JIRA_PAT = os.environ.get("JIRA_PAT", "")
_JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "")
_CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE", True)

_HEADERS = {
    "Authorization": f"Bearer {_JIRA_PAT}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def create_issue(payload: JiraIssuePayload) -> str:
    url = f"{_JIRA_URL}/rest/api/2/issue"
    body = {
        "fields": {
            "project": {"key": _JIRA_PROJECT_KEY},
            "summary": payload.summary,
            "description": payload.description,
            "issuetype": {"name": payload.issueType},
            "priority": {"name": payload.priority},
        }
    }
    response = requests.post(url, json=body, headers=_HEADERS, verify=_CA_BUNDLE)
    response.raise_for_status()
    return response.json()["key"]
