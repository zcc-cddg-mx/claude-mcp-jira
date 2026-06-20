from fastapi import APIRouter, Header, HTTPException, Request

from ..audit import log
from ..clients import create_issue, parse_create_issue
from ..schemas import CreateIssueRequest, CreateIssueResponse

router = APIRouter(prefix="/issues", tags=["issues"])


@router.post("", response_model=CreateIssueResponse, status_code=201)
async def create_issue_endpoint(
    body: CreateIssueRequest,
    x_user: str = Header(default="anonymous"),
):
    try:
        payload = parse_create_issue(body.text)
    except Exception as e:
        log(user=x_user, action="create_issue", input_text=body.text,
            status="error", error=f"claude: {e}")
        raise HTTPException(status_code=422, detail=f"Claude parsing failed: {e}")

    try:
        key = create_issue(payload)
    except Exception as e:
        log(user=x_user, action="create_issue", input_text=body.text,
            claude_payload=payload.model_dump(), status="error", error=f"jira: {e}")
        raise HTTPException(status_code=502, detail=f"Jira request failed: {e}")

    log(
        user=x_user,
        action="create_issue",
        input_text=body.text,
        claude_payload=payload.model_dump(),
        jira_key=key,
        status="ok",
    )
    return CreateIssueResponse(
        key=key,
        summary=payload.summary,
        issueType=payload.issueType,
        priority=payload.priority,
    )
