from fastapi import APIRouter, Header, HTTPException

from ..audit import log, new_request_id
from ..clients import get_issue, parse_update_issue, rate_limit_check, update_issue
from ..schemas import UpdateIssueRequest, UpdateIssueResponse

router = APIRouter(prefix="/issues", tags=["issues"])


@router.patch("/{key}", response_model=UpdateIssueResponse)
async def update_issue_endpoint(
    key: str,
    body: UpdateIssueRequest,
    x_user: str = Header(default="anonymous"),
):
    rid = new_request_id()

    try:
        rate_limit_check(x_user)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    try:
        payload = parse_update_issue(body.text)
    except Exception as e:
        log(request_id=rid, user=x_user, action="update_issue", input_text=body.text,
            status="error", error=f"claude: {e}")
        raise HTTPException(status_code=422, detail=f"Claude parsing failed: {e}")

    try:
        update_issue(key, payload)
    except Exception as e:
        log(request_id=rid, user=x_user, action="update_issue", input_text=body.text,
            claude_payload=payload.model_dump(), status="error", error=f"jira: {e}")
        raise HTTPException(status_code=502, detail=f"Jira request failed: {e}")

    log(
        request_id=rid,
        user=x_user,
        action="update_issue",
        input_text=body.text,
        claude_payload=payload.model_dump(),
        jira_key=key,
        status="ok",
    )
    return UpdateIssueResponse(key=key, status="updated")
