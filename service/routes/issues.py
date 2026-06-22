from fastapi import APIRouter, Header, HTTPException

from ..audit import log, new_request_id
from ..clients import create_issue, parse_create_issue, rate_limit_check
from ..clients.project_config import resolve_project
from ..clients.sanitizer import sanitize
from ..schemas import CreateIssueRequest, CreateIssueResponse

router = APIRouter(prefix="/issues", tags=["issues"])


@router.post("", response_model=CreateIssueResponse, status_code=201)
async def create_issue_endpoint(
    body: CreateIssueRequest,
    x_user: str = Header(default="anonymous"),
):
    rid = new_request_id()

    try:
        rate_limit_check(x_user)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    try:
        project_key = resolve_project(body.project)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        payload = parse_create_issue(body.text, project_key)
    except Exception as e:
        log(request_id=rid, user=x_user, action="create_issue", input_text=body.text,
            status="error", error=f"claude: {e}")
        raise HTTPException(status_code=422, detail=f"Claude parsing failed: {sanitize(str(e))}")

    try:
        key = create_issue(payload, project_key)
    except Exception as e:
        log(request_id=rid, user=x_user, action="create_issue", input_text=body.text,
            claude_payload=payload.model_dump(), status="error", error=f"jira: {e}")
        raise HTTPException(status_code=502, detail=f"Jira request failed: {sanitize(str(e))}")

    log(
        request_id=rid,
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
