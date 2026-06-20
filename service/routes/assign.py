from fastapi import APIRouter, Header, HTTPException

from ..audit import log, new_request_id
from ..clients import assign_issue, parse_assign_issue, rate_limit_check
from ..clients.sanitizer import sanitize
from ..schemas import AssignIssueRequest, AssignIssueResponse

router = APIRouter(prefix="/issues", tags=["issues"])


@router.post("/{key}/assign", response_model=AssignIssueResponse)
async def assign_issue_endpoint(
    key: str,
    body: AssignIssueRequest,
    x_user: str = Header(default="anonymous"),
):
    rid = new_request_id()

    try:
        rate_limit_check(x_user)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    try:
        payload = parse_assign_issue(body.text)
    except Exception as e:
        log(request_id=rid, user=x_user, action="assign_issue", input_text=body.text,
            jira_key=key, status="error", error=f"claude: {e}")
        raise HTTPException(status_code=422, detail=f"Claude parsing failed: {sanitize(str(e))}")

    try:
        assign_issue(key, payload.assignee)
    except Exception as e:
        log(request_id=rid, user=x_user, action="assign_issue", input_text=body.text,
            claude_payload=payload.model_dump(), jira_key=key, status="error", error=f"jira: {e}")
        raise HTTPException(status_code=502, detail=f"Jira request failed: {sanitize(str(e))}")

    log(
        request_id=rid,
        user=x_user,
        action="assign_issue",
        input_text=body.text,
        claude_payload=payload.model_dump(),
        jira_key=key,
        status="ok",
    )
    return AssignIssueResponse(key=key, assignee=payload.assignee)
