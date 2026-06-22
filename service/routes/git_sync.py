import logging
import os

from fastapi import APIRouter, Header, HTTPException

from ..audit import log, new_request_id
from ..clients import log_work, parse_git_sync_fallback, rate_limit_check
from ..clients.sanitizer import sanitize
from ..schemas import GitSessionResult, GitSyncRequest, GitSyncResponse
from ..schemas.issue import LogWorkPayload
from ..git.scanner import get_commits, get_current_branch
from ..git.analyzer import group_sessions

_logger = logging.getLogger(__name__)

_GIT_CLAUDE_FALLBACK = os.environ.get("GIT_CLAUDE_FALLBACK", "true").lower() == "true"

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

    # Validate repo path — must be absolute and within filesystem (basic check)
    repo_path = body.repo_path.strip()
    if not os.path.isabs(repo_path):
        raise HTTPException(status_code=422, detail="repo_path debe ser una ruta absoluta.")

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

    # Build result sessions and optionally register worklogs
    result_sessions: list[GitSessionResult] = []
    worklogs_registered = 0

    for s in sessions_raw:
        registered = False
        if not body.dry_run and s["issue_key"]:
            payload = LogWorkPayload(
                time_spent_seconds=max(60, s["estimated_seconds"]),
                comment=_worklog_comment(s),
            )
            try:
                log_work(s["issue_key"], payload)
                registered = True
                worklogs_registered += 1
            except Exception as e:
                _logger.warning("git_sync: failed to log work on %s: %s", s["issue_key"], e)

        result_sessions.append(GitSessionResult(
            issue_key=s["issue_key"],
            estimated_hours=round(s["estimated_seconds"] / 3600, 2),
            estimated_seconds=s["estimated_seconds"],
            confidence=s["confidence"],
            messages=s["messages"],
            total_loc=s["total_loc"],
            commit_count=len(s["commits"]),
            worklog_registered=registered,
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
