import os

from ..schemas import SearchQueryStruct

_MAX_RESULTS = min(int(os.environ.get("JIRA_MAX_RESULTS", "50")), 50)

_DATE_RANGE_MAP = {
    "today": "startOfDay()",
    "last_week": "-7d",
    "last_month": "-30d",
}


def _jql_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_jql(struct: SearchQueryStruct) -> tuple[str, int]:
    """Returns (jql_string, max_results). MAX_RESULTS is always capped at 50."""
    clauses = []

    if struct.assignee:
        # currentUser() is a JQL function — pass through; otherwise quote
        if struct.assignee == "currentUser()":
            clauses.append("assignee = currentUser()")
        else:
            clauses.append(f'assignee = "{_jql_escape(struct.assignee)}"')

    if struct.status:
        clauses.append(f'status = "{_jql_escape(struct.status)}"')

    if struct.issuetype:
        clauses.append(f'issuetype = "{_jql_escape(struct.issuetype)}"')

    if struct.priority:
        clauses.append(f'priority = "{_jql_escape(struct.priority)}"')

    if struct.date_range:
        since = _DATE_RANGE_MAP.get(struct.date_range)
        if since:
            clauses.append(f"created >= {since}")

    if struct.text_search:
        clauses.append(f'text ~ "{_jql_escape(struct.text_search)}"')

    jql = " AND ".join(clauses) if clauses else "project is not EMPTY"
    jql += " ORDER BY created DESC"

    return jql, _MAX_RESULTS
