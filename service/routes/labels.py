from fastapi import APIRouter, Header, HTTPException

from ..audit import log, new_request_id
from ..clients import get_labels, parse_labels, rate_limit_check, update_labels
from ..clients.sanitizer import sanitize
from ..schemas import ActionsRequest, ActionsResponse

router = APIRouter(prefix="/issues", tags=["issues"])

_VALID_OPERATIONS = {"set", "add", "remove"}


@router.post("/{key}/labels", response_model=ActionsResponse)
async def labels_endpoint(
    key: str,
    body: ActionsRequest,
    x_user: str = Header(default="anonymous"),
):
    rid = new_request_id()

    try:
        rate_limit_check(x_user)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    try:
        current = get_labels(key)
    except Exception as e:
        log(request_id=rid, user=x_user, action="labels", input_text=body.text,
            jira_key=key, status="error", error=f"jira get_labels: {e}")
        raise HTTPException(status_code=502, detail=f"Jira request failed: {sanitize(str(e))}")

    try:
        payload = parse_labels(body.text, current)
    except Exception as e:
        log(request_id=rid, user=x_user, action="labels", input_text=body.text,
            jira_key=key, status="error", error=f"claude: {e}")
        raise HTTPException(status_code=422, detail=f"Claude parsing failed: {sanitize(str(e))}")

    if payload.operation not in _VALID_OPERATIONS:
        log(request_id=rid, user=x_user, action="labels", input_text=body.text,
            claude_payload=payload.model_dump(), jira_key=key, status="error",
            error=f"invalid operation: {payload.operation!r}")
        raise HTTPException(status_code=422, detail=f"Operación no válida: {payload.operation!r}. Use set, add o remove.")

    if payload.operation == "set":
        final = payload.labels
    elif payload.operation == "add":
        final = list(dict.fromkeys(current + payload.labels))
    else:
        remove_set = set(payload.labels)
        final = [l for l in current if l not in remove_set]

    try:
        update_labels(key, final)
    except Exception as e:
        log(request_id=rid, user=x_user, action="labels", input_text=body.text,
            claude_payload=payload.model_dump(), jira_key=key, status="error", error=f"jira: {e}")
        raise HTTPException(status_code=502, detail=f"Jira request failed: {sanitize(str(e))}")

    log(
        request_id=rid,
        user=x_user,
        action="labels",
        input_text=body.text,
        claude_payload=payload.model_dump(),
        jira_key=key,
        status="ok",
    )
    return ActionsResponse(key=key, action=f"labels_{payload.operation}", labels=final)
