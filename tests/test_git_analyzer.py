from datetime import datetime, timezone, timedelta

import pytest

from service.git.analyzer import group_sessions, _estimate_seconds, _confidence, _dominant_key


# ── Helpers ───────────────────────────────────────────────────────────────────

def _commit(message: str, ts: datetime, ins: int = 10, dels: int = 5) -> dict:
    return {
        "message": message,
        "timestamp": ts,
        "insertions": ins,
        "deletions": dels,
        "hash": "abc1234",
        "author": "dev@example.com",
    }


_T0 = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)


def _t(hours: float) -> datetime:
    return _T0 + timedelta(hours=hours)


# ── group_sessions: empty / single ───────────────────────────────────────────

def test_empty_commits_returns_empty():
    assert group_sessions([]) == []


def test_single_commit_creates_one_session():
    sessions = group_sessions([_commit("ZNRX-1 fix", _t(0))])
    assert len(sessions) == 1


def test_single_session_structure():
    c = _commit("ZNRX-1 fix", _t(0))
    s = group_sessions([c])[0]
    assert s["issue_key"] == "ZNRX-1"
    assert len(s["commits"]) == 1
    assert "estimated_seconds" in s
    assert "confidence" in s
    assert "messages" in s
    assert "total_loc" in s


# ── group_sessions: gap splitting ────────────────────────────────────────────

def test_commits_within_gap_are_one_session():
    # default gap = 120 min — commits 60 min apart should stay together
    commits = [
        _commit("ZNRX-1 a", _t(0)),
        _commit("ZNRX-1 b", _t(1)),
    ]
    assert len(group_sessions(commits)) == 1


def test_commits_beyond_gap_are_two_sessions():
    # 3 hours apart > 2 hour default gap
    commits = [
        _commit("ZNRX-1 morning", _t(0)),
        _commit("ZNRX-1 afternoon", _t(3)),
    ]
    assert len(group_sessions(commits)) == 2


def test_three_distinct_sessions():
    commits = [
        _commit("ZNRX-1 a", _t(0)),
        _commit("ZNRX-1 b", _t(4)),
        _commit("ZNRX-1 c", _t(8)),
    ]
    assert len(group_sessions(commits)) == 3


def test_commits_sorted_before_splitting():
    # Out-of-order timestamps — should still produce one session
    commits = [
        _commit("ZNRX-1 b", _t(1)),
        _commit("ZNRX-1 a", _t(0)),
    ]
    assert len(group_sessions(commits)) == 1


# ── group_sessions: issue key extraction ─────────────────────────────────────

def test_key_extracted_from_commit_message():
    sessions = group_sessions([_commit("ZNRX-99 feat", _t(0))])
    assert sessions[0]["issue_key"] == "ZNRX-99"


def test_key_extracted_from_branch_when_no_message_key():
    commits = [_commit("add feature", _t(0))]
    sessions = group_sessions(commits, branch="feature/ZNRX-55-auth")
    assert sessions[0]["issue_key"] == "ZNRX-55"


def test_no_key_returns_none():
    sessions = group_sessions([_commit("chore: cleanup", _t(0))], branch="main")
    assert sessions[0]["issue_key"] is None


def test_dominant_key_is_majority():
    commits = [
        _commit("ZNRX-1 fix a", _t(0)),
        _commit("ZNRX-1 fix b", _t(0.5)),
        _commit("ZNRX-2 side fix", _t(1)),
    ]
    sessions = group_sessions(commits)
    assert sessions[0]["issue_key"] == "ZNRX-1"


# ── group_sessions: confidence ────────────────────────────────────────────────

def test_confidence_high_when_key_in_message():
    sessions = group_sessions([_commit("ZNRX-1 fix", _t(0))])
    assert sessions[0]["confidence"] == "high"


def test_confidence_medium_when_key_only_in_branch():
    sessions = group_sessions([_commit("add feature", _t(0))], branch="ZNRX-55-feature")
    assert sessions[0]["confidence"] == "medium"


def test_confidence_low_when_no_key():
    sessions = group_sessions([_commit("chore", _t(0))], branch="main")
    assert sessions[0]["confidence"] == "low"


# ── group_sessions: total_loc ─────────────────────────────────────────────────

def test_total_loc_is_sum_of_insertions_and_deletions():
    commits = [
        _commit("ZNRX-1 a", _t(0), ins=100, dels=50),
        _commit("ZNRX-1 b", _t(1), ins=200, dels=10),
    ]
    s = group_sessions(commits)[0]
    assert s["total_loc"] == 360


# ── _estimate_seconds ─────────────────────────────────────────────────────────

def test_single_commit_returns_minimum():
    c = _commit("fix", _t(0))
    secs = _estimate_seconds([c])
    assert secs == 15 * 60  # MIN_SESSION_MINUTES default


def test_two_commits_span_used_as_base():
    commits = [_commit("a", _t(0)), _commit("b", _t(1))]  # 60 min span
    secs = _estimate_seconds(commits)
    assert secs == 60 * 60


def test_estimate_capped_at_max():
    # 10 hours apart → capped at MAX_SESSION_MINUTES (240 min)
    commits = [_commit("a", _t(0)), _commit("b", _t(10))]
    secs = _estimate_seconds(commits)
    assert secs == 240 * 60


def test_estimate_not_below_min():
    # Span of 5 min → clamped to MIN_SESSION_MINUTES (15 min)
    commits = [
        _commit("a", _t(0)),
        _commit("b", _T0 + timedelta(minutes=5)),
    ]
    secs = _estimate_seconds(commits)
    assert secs == 15 * 60


def test_loc_nudge_applied_when_above_threshold():
    # 60 min span, LOC > 200 → 60 * 1.2 = 72 min
    commits = [
        _commit("a", _t(0), ins=150, dels=100),  # 250 LOC > 200 threshold
        _commit("b", _t(1), ins=0, dels=0),
    ]
    secs = _estimate_seconds(commits)
    assert secs == int(72 * 60)


def test_loc_nudge_not_applied_below_threshold():
    # 60 min span, LOC = 50 → stays at 60 min
    commits = [
        _commit("a", _t(0), ins=25, dels=25),
        _commit("b", _t(1), ins=0, dels=0),
    ]
    secs = _estimate_seconds(commits)
    assert secs == 60 * 60


def test_loc_nudge_still_respects_cap():
    # 200 min span, big LOC → 200 * 1.2 = 240 → capped at 240
    commits = [
        _commit("a", _t(0), ins=1000, dels=500),
        _commit("b", _t(0) + timedelta(minutes=200), ins=0, dels=0),
    ]
    secs = _estimate_seconds(commits)
    assert secs == 240 * 60
