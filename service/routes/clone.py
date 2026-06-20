from fastapi import APIRouter, Header, HTTPException

from ..audit import log, new_request_id
from ..clients import clone_issue, get_issue, parse_clone_issue, rate_limit_check
from ..clients.sanitizer import sanitize
from ..schemas import CloneIssueRequest, CloneIssueResponse

router = APIRouter(prefix="/issues", tags=["issues"])


@router.post("/{key}/clone", response_model=CloneIssueResponse)
async def clone_issue_endpoint(
    key: str,
    body: CloneIssueRequest,
    x_user: str = Header(default="anonymous"),
):
    rid = new_request_id()

    try:
        rate_limit_check(x_user)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    try:
        source = get_issue(key)
    except Exception as e:
        log(request_id=rid, user=x_user, action="clone_issue", input_text=body.text,
            jira_key=key, status="error", error=f"jira get_issue: {e}")
        raise HTTPException(status_code=502, detail=f"Jira request failed: {sanitize(str(e))}")

    try:
        payload = parse_clone_issue(body.text, source)
    except Exception as e:
        log(request_id=rid, user=x_user, action="clone_issue", input_text=body.text,
            jira_key=key, status="error", error=f"claude: {e}")
        raise HTTPException(status_code=422, detail=f"Claude parsing failed: {sanitize(str(e))}")

    try:
        new_key = clone_issue(key, source, payload)
    except Exception as e:
        log(request_id=rid, user=x_user, action="clone_issue", input_text=body.text,
            claude_payload=payload.model_dump(), jira_key=key, status="error", error=f"jira: {e}")
        raise HTTPException(status_code=502, detail=f"Jira request failed: {sanitize(str(e))}")

    final_summary = payload.summary or source["fields"].get("summary", "")

    log(
        request_id=rid,
        user=x_user,
        action="clone_issue",
        input_text=body.text,
        claude_payload=payload.model_dump(),
        jira_key=key,
        status="ok",
    )
    return CloneIssueResponse(source_key=key, new_key=new_key, summary=final_summary)
