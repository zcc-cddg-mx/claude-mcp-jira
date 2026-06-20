from fastapi import APIRouter, Header, HTTPException

from ..audit import log, new_request_id
from ..clients import get_issue, rate_limit_check, summarize_issue
from ..clients.sanitizer import sanitize
from ..schemas import SummarizeIssueResponse

router = APIRouter(prefix="/issues", tags=["issues"])


@router.get("/{key}/summary", response_model=SummarizeIssueResponse)
async def summarize_issue_endpoint(
    key: str,
    x_user: str = Header(default="anonymous"),
):
    rid = new_request_id()

    try:
        rate_limit_check(x_user)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    try:
        issue_data = get_issue(key)
    except Exception as e:
        log(request_id=rid, user=x_user, action="summarize_issue", input_text=key,
            status="error", error=f"jira: {e}")
        raise HTTPException(status_code=502, detail=f"Jira request failed: {sanitize(str(e))}")

    try:
        summary = summarize_issue(issue_data)
    except Exception as e:
        log(request_id=rid, user=x_user, action="summarize_issue", input_text=key,
            status="error", error=f"claude: {e}")
        raise HTTPException(status_code=422, detail=f"Claude summarization failed: {sanitize(str(e))}")

    log(
        request_id=rid,
        user=x_user,
        action="summarize_issue",
        input_text=key,
        jira_key=key,
        status="ok",
    )
    return SummarizeIssueResponse(key=key, summary=summary)
