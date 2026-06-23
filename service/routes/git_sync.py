import logging
import os

from fastapi import APIRouter, Header, HTTPException

from ..audit import log, new_request_id
from ..clients import log_work, parse_git_sync_fallback, rate_limit_check
from ..clients.claude_client import parse_git_humanizer
from ..clients.sanitizer import sanitize
from ..schemas import GitSessionResult, GitSyncRequest, GitSyncResponse
from ..schemas.issue import LogWorkPayload
from ..git.scanner import get_commits, get_current_branch
from ..git.analyzer import group_sessions
from ..git.repo_registry import resolve_repo

_logger = logging.getLogger(__name__)

_GIT_CLAUDE_FALLBACK = os.environ.get("GIT_CLAUDE_FALLBACK", "true").lower() == "true"
_GIT_HUMANIZER = os.environ.get("GIT_HUMANIZER", "true").lower() == "true"

router = APIRouter(prefix="/git", tags=["git"])


@router.post("/sync", response_model=GitSyncResponse)
async def git_sync_endpoint(
    body: GitSyncRequest,
    x_user: str = Header(default="anonymous"),
):
    rid = new_request_id()

    try:
        rate_limit_check(x_user)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    # Resolve repo_path: explicit path > name lookup > registry default
    repo_entry = None
    if body.repo_name:
        repo_entry = resolve_repo(body.repo_name)
        if not repo_entry:
            raise HTTPException(status_code=404, detail=f"Repo '{body.repo_name}' no registrado. Usa POST /git/repos para registrarlo.")
        repo_path = repo_entry["repo_path"]
    elif body.repo_path:
        repo_path = body.repo_path.strip()
        # Also try to find matching registry entry by path for defaults
        repo_entry = resolve_repo(repo_path)
    else:
        # No path or name — try registry default
        repo_entry = resolve_repo(None)
        if not repo_entry:
            raise HTTPException(status_code=422, detail="Se requiere repo_path o repo_name, o registra un repo por defecto.")
        repo_path = repo_entry["repo_path"]

    if not os.path.isabs(repo_path):
        raise HTTPException(status_code=422, detail="repo_path debe ser una ruta absoluta.")

    _registry_default_key = repo_entry["default_issue_key"] if repo_entry else None

    # Read commits
    _input = f"repo={repo_path} days={body.since_days} dry_run={body.dry_run}"

    try:
        commits = get_commits(repo_path, since_days=body.since_days, author=body.author)
    except ValueError as e:
        log(request_id=rid, user=x_user, action="git_sync", input_text=_input, status="error", error=str(e))
        raise HTTPException(status_code=422, detail=sanitize(str(e)))
    except Exception as e:
        log(request_id=rid, user=x_user, action="git_sync", input_text=_input, status="error", error=f"scanner: {e}")
        raise HTTPException(status_code=502, detail=f"Error leyendo repo: {sanitize(str(e))}")

    branch = get_current_branch(repo_path)
    sessions_raw = group_sessions(commits, branch=branch)

    # Claude fallback for sessions without a key
    if _GIT_CLAUDE_FALLBACK:
        for s in sessions_raw:
            if not s["issue_key"]:
                try:
                    s["issue_key"] = parse_git_sync_fallback(s["messages"], branch)
                except Exception as e:
                    _logger.warning("git_sync fallback failed: %s", e)

    # Registry default_issue_key fallback: if still no key, use repo default
    if _registry_default_key:
        for s in sessions_raw:
            if not s["issue_key"]:
                s["issue_key"] = _registry_default_key
                s["confidence"] = "low"

    # Claude humanizer: adjust time estimates with semantic signals from commit messages
    if _GIT_HUMANIZER:
        for s in sessions_raw:
            try:
                result = parse_git_humanizer(s)
                s["humanizer_adjusted_seconds"] = int(result["adjusted_hours"] * 3600)
                s["humanizer_reason"] = result["reason"]
            except Exception as e:
                _logger.warning("git_sync humanizer failed: %s", e)
                s["humanizer_adjusted_seconds"] = s["estimated_seconds"]
                s["humanizer_reason"] = None

    # Build result sessions and optionally register worklogs
    result_sessions: list[GitSessionResult] = []
    worklogs_registered = 0

    for s in sessions_raw:
        # Use humanizer-adjusted seconds if available, else algorithmic estimate
        final_seconds = s.get("humanizer_adjusted_seconds", s["estimated_seconds"])
        registered = False
        if not body.dry_run and s["issue_key"]:
            payload = LogWorkPayload(
                time_spent_seconds=max(60, final_seconds),
                comment=_worklog_comment(s),
            )
            try:
                log_work(s["issue_key"], payload)
                registered = True
                worklogs_registered += 1
            except Exception as e:
                _logger.warning("git_sync: failed to log work on %s: %s", s["issue_key"], e)

        base_secs = s["estimated_seconds"]
        result_sessions.append(GitSessionResult(
            issue_key=s["issue_key"],
            estimated_hours=round(final_seconds / 3600, 2),
            estimated_seconds=final_seconds,
            base_estimated_hours=round(base_secs / 3600, 2) if final_seconds != base_secs else None,
            confidence=s["confidence"],
            messages=s["messages"],
            total_loc=s["total_loc"],
            commit_count=len(s["commits"]),
            worklog_registered=registered,
            humanizer_reason=s.get("humanizer_reason"),
        ))

    sessions_with_key = sum(1 for s in result_sessions if s.issue_key)
    sessions_without_key = len(result_sessions) - sessions_with_key

    log(
        request_id=rid,
        user=x_user,
        action="git_sync",
        input_text=_input,
        status="ok",
    )

    return GitSyncResponse(
        repo_path=repo_path,
        since_days=body.since_days,
        dry_run=body.dry_run,
        branch=branch,
        total_commits=len(commits),
        sessions=result_sessions,
        sessions_with_key=sessions_with_key,
        sessions_without_key=sessions_without_key,
        worklogs_registered=worklogs_registered,
    )


def _worklog_comment(session: dict) -> str:
    msgs = session["messages"]
    if len(msgs) == 1:
        return msgs[0][:255]
    return f"{len(msgs)} commits: " + "; ".join(m[:80] for m in msgs[:3])
