from fastapi import APIRouter, Header, HTTPException

from ..audit import log, new_request_id
from ..clients import log_work, parse_log_work, rate_limit_check
from ..clients.sanitizer import sanitize
from ..schemas import LogWorkRequest, LogWorkResponse

router = APIRouter(prefix="/issues", tags=["issues"])


@router.post("/{key}/worklog", response_model=LogWorkResponse)
async def log_work_endpoint(
    key: str,
    body: LogWorkRequest,
    x_user: str = Header(default="anonymous"),
):
    rid = new_request_id()

    try:
        rate_limit_check(x_user)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    try:
        payload = parse_log_work(body.text)
    except Exception as e:
        log(request_id=rid, user=x_user, action="log_work", input_text=body.text,
            jira_key=key, status="error", error=f"claude: {e}")
        raise HTTPException(status_code=422, detail=f"Claude parsing failed: {sanitize(str(e))}")

    try:
        log_work(key, payload)
    except Exception as e:
        log(request_id=rid, user=x_user, action="log_work", input_text=body.text,
            claude_payload=payload.model_dump(), jira_key=key, status="error", error=f"jira: {e}")
        raise HTTPException(status_code=502, detail=f"Jira request failed: {sanitize(str(e))}")

    log(
        request_id=rid,
        user=x_user,
        action="log_work",
        input_text=body.text,
        claude_payload=payload.model_dump(),
        jira_key=key,
        status="ok",
    )
    return LogWorkResponse(
        key=key,
        time_spent_seconds=payload.time_spent_seconds,
        comment=payload.comment,
    )
