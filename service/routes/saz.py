from fastapi import APIRouter, Header, HTTPException

from ..audit import log, new_request_id
from ..clients import create_saz_issue, parse_saz_request, rate_limit_check
from ..clients.sanitizer import sanitize
from ..schemas import CreateSAZRequest, CreateSAZResponse

router = APIRouter(prefix="/issues", tags=["saz"])


@router.post("/saz", response_model=CreateSAZResponse)
async def create_saz_endpoint(
    body: CreateSAZRequest,
    x_user: str = Header(default="anonymous"),
):
    rid = new_request_id()

    try:
        rate_limit_check(x_user)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    try:
        payload = parse_saz_request(body.text)
    except Exception as e:
        log(request_id=rid, user=x_user, action="create_saz", input_text=body.text,
            jira_key="SAZ", status="error", error=f"claude: {e}")
        raise HTTPException(status_code=422, detail=f"Claude parsing failed: {sanitize(str(e))}")

    try:
        saz_key = create_saz_issue(payload, znrx_key=body.znrx_key)
    except Exception as e:
        log(request_id=rid, user=x_user, action="create_saz", input_text=body.text,
            claude_payload=payload.model_dump(), jira_key="SAZ", status="error", error=f"jira: {e}")
        raise HTTPException(status_code=502, detail=f"Jira request failed: {sanitize(str(e))}")

    status = "linked" if body.znrx_key else "created"
    log(
        request_id=rid,
        user=x_user,
        action="create_saz",
        input_text=body.text,
        claude_payload=payload.model_dump(),
        jira_key=saz_key,
        status="ok",
    )
    return CreateSAZResponse(
        saz_key=saz_key,
        znrx_key=body.znrx_key,
        summary=payload.summary,
        status=status,
    )
