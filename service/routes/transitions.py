from fastapi import APIRouter, Header, HTTPException

from ..audit import log, new_request_id
from ..clients import get_transitions, parse_transition_issue, rate_limit_check, transition_issue
from ..clients.sanitizer import sanitize
from ..schemas import TransitionIssueRequest, TransitionIssueResponse

router = APIRouter(prefix="/issues", tags=["issues"])


@router.post("/{key}/transition", response_model=TransitionIssueResponse)
async def transition_issue_endpoint(
    key: str,
    body: TransitionIssueRequest,
    x_user: str = Header(default="anonymous"),
):
    rid = new_request_id()

    try:
        rate_limit_check(x_user)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    try:
        available = get_transitions(key)
    except Exception as e:
        log(request_id=rid, user=x_user, action="transition_issue", input_text=body.text,
            jira_key=key, status="error", error=f"jira get_transitions: {e}")
        raise HTTPException(status_code=502, detail=f"Jira request failed: {sanitize(str(e))}")

    if not available:
        log(request_id=rid, user=x_user, action="transition_issue", input_text=body.text,
            jira_key=key, status="error", error="no transitions available")
        raise HTTPException(status_code=422, detail="No hay transiciones disponibles para este ticket en su estado actual.")

    try:
        payload = parse_transition_issue(body.text, available)
    except Exception as e:
        log(request_id=rid, user=x_user, action="transition_issue", input_text=body.text,
            jira_key=key, status="error", error=f"claude: {e}")
        raise HTTPException(status_code=422, detail=f"Claude parsing failed: {sanitize(str(e))}")

    valid_ids = {t["id"] for t in available}
    if payload.transition_id not in valid_ids:
        names = ", ".join(t["name"] for t in available)
        log(request_id=rid, user=x_user, action="transition_issue", input_text=body.text,
            claude_payload=payload.model_dump(), jira_key=key, status="error",
            error=f"transition_id {payload.transition_id!r} not in available")
        raise HTTPException(
            status_code=422,
            detail=f"Transición no disponible. Estados alcanzables desde el estado actual: {names}",
        )

    try:
        new_status = transition_issue(key, payload)
    except Exception as e:
        log(request_id=rid, user=x_user, action="transition_issue", input_text=body.text,
            claude_payload=payload.model_dump(), jira_key=key, status="error", error=f"jira: {e}")
        raise HTTPException(status_code=502, detail=f"Jira request failed: {sanitize(str(e))}")

    log(
        request_id=rid,
        user=x_user,
        action="transition_issue",
        input_text=body.text,
        claude_payload=payload.model_dump(),
        jira_key=key,
        status="ok",
    )
    return TransitionIssueResponse(key=key, status=new_status, transition=payload.transition_name)
