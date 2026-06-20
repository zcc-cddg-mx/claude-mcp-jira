from fastapi import APIRouter, Header, HTTPException

from ..audit import log, new_request_id
from ..clients import add_comment, parse_add_comment, rate_limit_check
from ..clients.sanitizer import sanitize
from ..schemas import AddCommentRequest, AddCommentResponse

router = APIRouter(prefix="/issues", tags=["issues"])


@router.post("/{key}/comments", response_model=AddCommentResponse)
async def add_comment_endpoint(
    key: str,
    body: AddCommentRequest,
    x_user: str = Header(default="anonymous"),
):
    rid = new_request_id()

    try:
        rate_limit_check(x_user)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    try:
        payload = parse_add_comment(body.text)
    except Exception as e:
        log(request_id=rid, user=x_user, action="add_comment", input_text=body.text,
            jira_key=key, status="error", error=f"claude: {e}")
        raise HTTPException(status_code=422, detail=f"Claude parsing failed: {sanitize(str(e))}")

    try:
        add_comment(key, payload.comment)
    except Exception as e:
        log(request_id=rid, user=x_user, action="add_comment", input_text=body.text,
            claude_payload=payload.model_dump(), jira_key=key, status="error", error=f"jira: {e}")
        raise HTTPException(status_code=502, detail=f"Jira request failed: {sanitize(str(e))}")

    log(
        request_id=rid,
        user=x_user,
        action="add_comment",
        input_text=body.text,
        claude_payload=payload.model_dump(),
        jira_key=key,
        status="ok",
    )
    return AddCommentResponse(key=key, comment=payload.comment)
