"""
Read commits from a local Git repository.
Returns only metadata — no code content ever leaves this module.
"""

import subprocess
from datetime import datetime, timezone
from typing import Optional


def get_commits(repo_path: str, since_days: int = 1, author: Optional[str] = None) -> list[dict]:
    """
    Return commits from the repo since N days ago as a list of dicts:
      {hash, author_email, message, timestamp (UTC), files_changed, insertions, deletions}

    Uses subprocess + git log — no gitpython dependency required.
    Raises ValueError if repo_path is not a valid git repository.
    """
    since_arg = f"--since={since_days} days ago"
    author_arg = [f"--author={author}"] if author else []

    # Separator unlikely to appear in commit messages
    SEP = "|||GIT_SEP|||"
    FMT = SEP.join(["%H", "%ae", "%aI", "%s"])

    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "log", "--format=" + FMT, since_arg, *author_arg],
            capture_output=True, text=True, timeout=30,
        )
    except FileNotFoundError:
        raise ValueError("git not found in PATH")
    except subprocess.TimeoutExpired:
        raise ValueError(f"git log timed out for repo: {repo_path}")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise ValueError(f"Not a git repository or git error: {stderr or repo_path}")

    if not result.stdout.strip():
        return []

    commits = []
    for line in result.stdout.strip().splitlines():
        parts = line.split(SEP)
        if len(parts) != 4:
            continue
        hash_, email, ts_str, message = parts
        try:
            ts = datetime.fromisoformat(ts_str)
        except ValueError:
            continue

        # Stat: count changed lines per commit (metadata only — no diff content)
        stat = _get_stat(repo_path, hash_)

        commits.append({
            "hash": hash_[:8],
            "author_email": email,
            "message": message,
            "timestamp": ts.astimezone(timezone.utc),
            "files_changed": stat["files"],
            "insertions": stat["insertions"],
            "deletions": stat["deletions"],
        })

    return commits


def _get_stat(repo_path: str, commit_hash: str) -> dict:
    """Return files_changed, insertions, deletions for a single commit."""
    try:
        r = subprocess.run(
            ["git", "-C", repo_path, "show", "--stat", "--format=", commit_hash],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            return {"files": 0, "insertions": 0, "deletions": 0}
        last_line = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        files = insertions = deletions = 0
        import re
        m_files = re.search(r"(\d+) file", last_line)
        m_ins = re.search(r"(\d+) insertion", last_line)
        m_del = re.search(r"(\d+) deletion", last_line)
        if m_files:
            files = int(m_files.group(1))
        if m_ins:
            insertions = int(m_ins.group(1))
        if m_del:
            deletions = int(m_del.group(1))
        return {"files": files, "insertions": insertions, "deletions": deletions}
    except Exception:
        return {"files": 0, "insertions": 0, "deletions": 0}


def get_current_branch(repo_path: str) -> Optional[str]:
    """Return the current branch name, or None on error."""
    try:
        r = subprocess.run(
            ["git", "-C", repo_path, "branch", "--show-current"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() or None
    except Exception:
        return None
