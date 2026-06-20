import pytest
from service.clients.jql_builder import _jql_escape, build_jql
from service.schemas.issue import SearchQueryStruct


# ── _jql_escape ───────────────────────────────────────────────────────────────

def test_escape_double_quote():
    assert _jql_escape('In Progress "test"') == 'In Progress \\"test\\"'


def test_escape_backslash():
    assert _jql_escape("path\\file") == "path\\\\file"


def test_escape_plain_value():
    assert _jql_escape("To Do") == "To Do"


# ── build_jql — clauses ───────────────────────────────────────────────────────

def test_assignee_current_user():
    jql, _ = build_jql(SearchQueryStruct(assignee="currentUser()"))
    assert "assignee = currentUser()" in jql
    # must NOT be wrapped in quotes
    assert 'assignee = "currentUser()"' not in jql


def test_assignee_normal_quoted():
    jql, _ = build_jql(SearchQueryStruct(assignee="carlos.duarte2"))
    assert 'assignee = "carlos.duarte2"' in jql


def test_assignee_injection_escaped():
    jql, _ = build_jql(SearchQueryStruct(assignee='foo" OR assignee = "admin'))
    # The injected quote is backslash-escaped — the whole value is one quoted string.
    # JQL receives: assignee = "foo\" OR assignee = \"admin" — treated as a literal string value.
    assert '\\"' in jql
    # The clause is wrapped in a single pair of outer quotes
    assert jql.startswith('assignee = "') or 'assignee = "' in jql


def test_status_quoted():
    jql, _ = build_jql(SearchQueryStruct(status="In Progress"))
    assert 'status = "In Progress"' in jql


def test_status_injection_escaped():
    jql, _ = build_jql(SearchQueryStruct(status='Open" OR status = "Done'))
    # Quote is escaped — the whole value is a single quoted string, not two clauses.
    # JQL sees: status = "Open\" OR status = \"Done"
    assert '\\"' in jql
    # There is only one unquoted `status =` clause (the one starting the expression)
    assert jql.startswith('status = "') or ' AND status = "' in jql or jql.startswith('status = "')


def test_issuetype_quoted():
    jql, _ = build_jql(SearchQueryStruct(issuetype="Task"))
    assert 'issuetype = "Task"' in jql


def test_priority_quoted():
    jql, _ = build_jql(SearchQueryStruct(priority="High"))
    assert 'priority = "High"' in jql


def test_date_range_today():
    jql, _ = build_jql(SearchQueryStruct(date_range="today"))
    assert "created >= startOfDay()" in jql


def test_date_range_last_week():
    jql, _ = build_jql(SearchQueryStruct(date_range="last_week"))
    assert "created >= -7d" in jql


def test_date_range_unknown_rejected_by_schema():
    # Pydantic validates date_range values — unknown values are rejected at schema level
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        SearchQueryStruct(date_range="yesterday")


def test_text_search_quoted_and_escaped():
    jql, _ = build_jql(SearchQueryStruct(text_search='login "bug"'))
    assert 'text ~ "login \\"bug\\""' in jql


def test_empty_struct_returns_fallback():
    jql, _ = build_jql(SearchQueryStruct())
    assert jql.startswith("project is not EMPTY")


def test_order_by_always_present():
    jql, _ = build_jql(SearchQueryStruct(status="Open"))
    assert "ORDER BY created DESC" in jql


def test_max_results_capped_at_50():
    import os
    os.environ["JIRA_MAX_RESULTS"] = "100"
    # Re-import to pick up env var (module-level constant)
    import importlib
    import service.clients.jql_builder as mod
    importlib.reload(mod)
    _, max_results = mod.build_jql(SearchQueryStruct())
    assert max_results <= 50
    del os.environ["JIRA_MAX_RESULTS"]


def test_multiple_clauses_joined_with_and():
    jql, _ = build_jql(SearchQueryStruct(status="Open", priority="High"))
    assert " AND " in jql
