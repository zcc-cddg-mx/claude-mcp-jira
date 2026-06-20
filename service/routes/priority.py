from fastapi import APIRouter, Header, HTTPException

from ..audit import log, new_request_id
from ..clients import parse_set_priority, rate_limit_check, set_priority
from ..clients.sanitizer import sanitize
from ..schemas import SetPriorityRequest, SetPriorityResponse

router = APIRouter(prefix="/issues", tags=["issues"])


@router.post("/{key}/priority", response_model=SetPriorityResponse)
async def set_priority_endpoint(
    key: str,
    body: SetPriorityRequest,
    x_user: str = Header(default="anonymous"),
):
    rid = new_request_id()

    try:
        rate_limit_check(x_user)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    try:
        payload = parse_set_priority(body.text)
    except Exception as e:
        log(request_id=rid, user=x_user, action="set_priority", input_text=body.text,
            jira_key=key, status="error", error=f"claude: {e}")
        raise HTTPException(status_code=422, detail=f"Claude parsing failed: {sanitize(str(e))}")

    try:
        set_priority(key, payload.priority)
    except Exception as e:
        log(request_id=rid, user=x_user, action="set_priority", input_text=body.text,
            claude_payload=payload.model_dump(), jira_key=key, status="error", error=f"jira: {e}")
        raise HTTPException(status_code=502, detail=f"Jira request failed: {sanitize(str(e))}")

    log(
        request_id=rid,
        user=x_user,
        action="set_priority",
        input_text=body.text,
        claude_payload=payload.model_dump(),
        jira_key=key,
        status="ok",
    )
    return SetPriorityResponse(key=key, priority=payload.priority)
