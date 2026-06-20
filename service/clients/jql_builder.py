from ..schemas import SearchQueryStruct

_MAX_RESULTS = 50

_DATE_RANGE_MAP = {
    "today": "startOfDay()",
    "last_week": "-7d",
    "last_month": "-30d",
}


def build_jql(struct: SearchQueryStruct) -> tuple[str, int]:
    """Returns (jql_string, max_results). MAX_RESULTS is always capped at 50."""
    clauses = []

    if struct.assignee:
        clauses.append(f'assignee = {struct.assignee}')

    if struct.status:
        clauses.append(f'status = "{struct.status}"')

    if struct.issuetype:
        clauses.append(f'issuetype = "{struct.issuetype}"')

    if struct.priority:
        clauses.append(f'priority = "{struct.priority}"')

    if struct.date_range:
        since = _DATE_RANGE_MAP.get(struct.date_range)
        if since:
            clauses.append(f"created >= {since}")

    if struct.text_search:
        safe = struct.text_search.replace('"', '\\"')
        clauses.append(f'text ~ "{safe}"')

    jql = " AND ".join(clauses) if clauses else "project is not EMPTY"
    jql += " ORDER BY created DESC"

    return jql, _MAX_RESULTS
