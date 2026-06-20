from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Optional

from ..audit import log, new_request_id
from ..clients import rate_limit_check

router = APIRouter(prefix="/issues", tags=["issues"])

_VALID_ACTIONS = {
    "add_watcher",
    "link_issue",
    "set_fix_version",
    "set_component",
    "update_custom_field",
}


class ActionRequest(BaseModel):
    action: str = Field(..., description="One of: " + ", ".join(sorted(_VALID_ACTIONS)))
    params: Optional[dict[str, Any]] = None


class ActionResponse(BaseModel):
    key: str
    action: str
    status: str


@router.post("/{key}/actions", response_model=ActionResponse)
async def actions_endpoint(
    key: str,
    body: ActionRequest,
    x_user: str = Header(default="anonymous"),
):
    rid = new_request_id()

    try:
        rate_limit_check(x_user)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    if body.action not in _VALID_ACTIONS:
        log(request_id=rid, user=x_user, action=f"actions:{body.action}", input_text=body.action,
            jira_key=key, status="error", error=f"unknown action: {body.action!r}")
        raise HTTPException(
            status_code=422,
            detail=f"Acción no válida: {body.action!r}. Acciones disponibles: {', '.join(sorted(_VALID_ACTIONS))}",
        )

    log(request_id=rid, user=x_user, action=f"actions:{body.action}", input_text=body.action,
        jira_key=key, status="error", error="not_implemented")
    raise HTTPException(
        status_code=501,
        detail=f"Acción '{body.action}' reconocida pero aún no implementada.",
    )
