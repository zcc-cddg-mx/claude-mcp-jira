"""Unit tests for Fase 8a: per-request PAT routing via ContextVar."""
import asyncio

import pytest

from service.clients.jira_client import _JIRA_PAT, _get_headers, _request_pat


def test_headers_use_env_pat_by_default():
    """When no ContextVar is set, _get_headers uses JIRA_PAT from env."""
    headers = _get_headers()
    assert headers["Authorization"] == f"Bearer {_JIRA_PAT}"
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"


def test_headers_use_contextvar_when_set():
    """When _request_pat is set in ContextVar, _get_headers uses that value."""
    custom_pat = "test-custom-pat-xyz"
    tok = _request_pat.set(custom_pat)
    try:
        headers = _get_headers()
        assert headers["Authorization"] == f"Bearer {custom_pat}"
    finally:
        _request_pat.reset(tok)


def test_contextvar_reset_after_request():
    """After resetting the ContextVar, _get_headers falls back to env PAT."""
    custom_pat = "test-custom-pat-xyz"
    tok = _request_pat.set(custom_pat)
    _request_pat.reset(tok)
    headers = _get_headers()
    assert headers["Authorization"] == f"Bearer {_JIRA_PAT}"


def test_contextvar_isolation_between_tasks():
    """Two concurrent async tasks each see their own ContextVar value."""
    results = {}

    async def task_a():
        tok = _request_pat.set("pat-for-a")
        try:
            await asyncio.sleep(0)  # yield to allow task_b to run
            results["a"] = _get_headers()["Authorization"]
        finally:
            _request_pat.reset(tok)

    async def task_b():
        tok = _request_pat.set("pat-for-b")
        try:
            await asyncio.sleep(0)
            results["b"] = _get_headers()["Authorization"]
        finally:
            _request_pat.reset(tok)

    async def run():
        await asyncio.gather(task_a(), task_b())

    asyncio.run(run())
    assert results["a"] == "Bearer pat-for-a"
    assert results["b"] == "Bearer pat-for-b"


def test_contextvar_none_falls_back_to_env():
    """Explicitly setting ContextVar to None falls back to env PAT."""
    tok = _request_pat.set(None)
    try:
        headers = _get_headers()
        assert headers["Authorization"] == f"Bearer {_JIRA_PAT}"
    finally:
        _request_pat.reset(tok)


def test_contextvar_empty_string_falls_back_to_env():
    """Setting ContextVar to empty string falls back to env PAT (or uses empty).

    _get_headers uses 'pat = _request_pat.get() or _JIRA_PAT', so empty string
    is falsy and falls back to env.
    """
    tok = _request_pat.set("")
    try:
        headers = _get_headers()
        # Empty string is falsy → falls back to env PAT
        assert headers["Authorization"] == f"Bearer {_JIRA_PAT}"
    finally:
        _request_pat.reset(tok)


def test_pat_not_logged_in_headers():
    """The Authorization header value is never exposed in other header fields."""
    custom_pat = "super-secret-pat"
    tok = _request_pat.set(custom_pat)
    try:
        headers = _get_headers()
        # PAT should only appear in Authorization, not in any other header
        other_values = [v for k, v in headers.items() if k != "Authorization"]
        for v in other_values:
            assert custom_pat not in v
    finally:
        _request_pat.reset(tok)
