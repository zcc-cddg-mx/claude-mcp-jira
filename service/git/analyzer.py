"""
Group commits into work sessions and estimate time spent per session.

Rules:
  - Commits are sorted by timestamp ascending.
  - Gap > SESSION_GAP_MINUTES between consecutive commits starts a new session.
  - Each session has a minimum of MIN_SESSION_MINUTES and a cap of MAX_SESSION_MINUTES.
  - LOC count (insertions + deletions) can nudge the estimate up by up to LOC_FACTOR.
"""

import os
from datetime import timedelta
from typing import Optional

from .mapper import extract_issue_key

_SESSION_GAP_MINUTES = int(os.environ.get("GIT_SESSION_GAP_MINUTES", "120"))
_MIN_SESSION_MINUTES = int(os.environ.get("GIT_MIN_SESSION_MINUTES", "15"))
_MAX_SESSION_MINUTES = int(os.environ.get("GIT_MAX_SESSION_MINUTES", "240"))
_LOC_NUDGE_THRESHOLD = int(os.environ.get("GIT_LOC_NUDGE_THRESHOLD", "200"))


def group_sessions(commits: list[dict], branch: Optional[str] = None) -> list[dict]:
    """
    Return a list of sessions, each with:
      {
        issue_key: str | None,
        commits: [list of commit dicts],
        estimated_seconds: int,
        confidence: "high" | "medium" | "low",
        messages: [list of commit messages],
        total_loc: int,
      }
    """
    if not commits:
        return []

    sorted_commits = sorted(commits, key=lambda c: c["timestamp"])
    gap = timedelta(minutes=_SESSION_GAP_MINUTES)

    # Split into raw sessions by time gap
    raw_sessions: list[list[dict]] = []
    current: list[dict] = [sorted_commits[0]]
    for c in sorted_commits[1:]:
        if c["timestamp"] - current[-1]["timestamp"] > gap:
            raw_sessions.append(current)
            current = [c]
        else:
            current.append(c)
    raw_sessions.append(current)

    sessions = []
    for raw in raw_sessions:
        issue_key = _dominant_key(raw, branch)
        confidence = _confidence(raw, issue_key)
        estimated = _estimate_seconds(raw)
        total_loc = sum(c["insertions"] + c["deletions"] for c in raw)
        sessions.append({
            "issue_key": issue_key,
            "commits": raw,
            "estimated_seconds": estimated,
            "confidence": confidence,
            "messages": [c["message"] for c in raw],
            "total_loc": total_loc,
        })

    return sessions


def _dominant_key(commits: list[dict], branch: Optional[str]) -> Optional[str]:
    """Return the most frequent issue key across commits in the session, or the branch key."""
    counts: dict[str, int] = {}
    for c in commits:
        k = extract_issue_key(c["message"], branch)
        if k:
            counts[k] = counts.get(k, 0) + 1
    if not counts:
        return None
    return max(counts, key=lambda k: counts[k])


def _estimate_seconds(commits: list[dict]) -> int:
    """Estimate total work time in seconds for a session."""
    if len(commits) == 1:
        # Single commit: use minimum session time
        base = timedelta(minutes=_MIN_SESSION_MINUTES)
    else:
        first = commits[0]["timestamp"]
        last = commits[-1]["timestamp"]
        base = last - first

    minutes = base.total_seconds() / 60

    # Nudge up if LOC is large
    total_loc = sum(c["insertions"] + c["deletions"] for c in commits)
    if total_loc > _LOC_NUDGE_THRESHOLD:
        minutes *= 1.2

    # Clamp
    minutes = max(_MIN_SESSION_MINUTES, min(_MAX_SESSION_MINUTES, minutes))

    return int(minutes * 60)


def _confidence(commits: list[dict], issue_key: Optional[str]) -> str:
    if not issue_key:
        return "low"
    # High confidence: key appears in commit message (not just branch)
    for c in commits:
        from .mapper import _KEY_PATTERN
        if _KEY_PATTERN.search(c["message"]):
            return "high"
    # Key came only from branch name
    return "medium"
