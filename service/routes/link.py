from fastapi import APIRouter, Header, HTTPException

from ..audit import log, new_request_id
from ..clients import link_issue, parse_link_issue, rate_limit_check
from ..clients.sanitizer import sanitize
from ..schemas import LinkIssueRequest, LinkIssueResponse

router = APIRouter(prefix="/issues", tags=["issues"])


@router.post("/{key}/link", response_model=LinkIssueResponse)
async def link_issue_endpoint(
    key: str,
    body: LinkIssueRequest,
    x_user: str = Header(default="anonymous"),
):
    rid = new_request_id()

    try:
        rate_limit_check(x_user)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    try:
        payload = parse_link_issue(body.text)
    except Exception as e:
        log(request_id=rid, user=x_user, action="link_issue", input_text=body.text,
            jira_key=key, status="error", error=f"claude: {e}")
        raise HTTPException(status_code=422, detail=f"Claude parsing failed: {sanitize(str(e))}")

    try:
        link_issue(key, payload.target_key, payload.link_type_id, payload.source_is_outward)
    except Exception as e:
        log(request_id=rid, user=x_user, action="link_issue", input_text=body.text,
            claude_payload=payload.model_dump(), jira_key=key, status="error", error=f"jira: {e}")
        raise HTTPException(status_code=502, detail=f"Jira request failed: {sanitize(str(e))}")

    log(
        request_id=rid,
        user=x_user,
        action="link_issue",
        input_text=body.text,
        claude_payload=payload.model_dump(),
        jira_key=key,
        status="ok",
    )
    return LinkIssueResponse(
        source_key=key,
        target_key=payload.target_key,
        link_type_id=payload.link_type_id,
    )
