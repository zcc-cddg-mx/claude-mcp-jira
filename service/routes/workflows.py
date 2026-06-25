import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from ..audit import log, new_request_id
from ..clients.sanitizer import sanitize
from ..clients.workflow_store import create_execution, get_execution, list_executions, update_execution
from ..schemas.workflow_schemas import (
    CreateFeaturePRRequest,
    WorkflowExecutionResponse,
    WorkflowUpdateRequest,
)

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _to_response(d: dict) -> WorkflowExecutionResponse:
    return WorkflowExecutionResponse(**d)


@router.post("/create-feature-pr", response_model=WorkflowExecutionResponse, status_code=201)
async def create_workflow(
    body: CreateFeaturePRRequest,
    x_user: str = Header("anonymous"),
):
    rid = new_request_id()
    user = sanitize(x_user)
    try:
        execution = create_execution(
            workflow_type="create_feature_pr",
            issue_key=body.issue_key,
            user=user,
        )
        log(request_id=rid, user=user, action="workflow_create", status="ok",
            input_text=f"issue_key={body.issue_key}", jira_key=execution["execution_id"])
        return _to_response(execution)
    except Exception as e:
        log(request_id=rid, user=user, action="workflow_create", status="error",
            input_text=f"issue_key={body.issue_key}", error=sanitize(str(e)))
        raise HTTPException(status_code=500, detail=sanitize(str(e)))


@router.get("", response_model=list[WorkflowExecutionResponse])
async def list_workflows(
    issue_key: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    x_user: str = Header("anonymous"),
):
    executions = list_executions(issue_key=issue_key, status=status, limit=limit)
    return [_to_response(e) for e in executions]


@router.get("/{execution_id}", response_model=WorkflowExecutionResponse)
async def get_workflow(
    execution_id: str,
    x_user: str = Header("anonymous"),
):
    execution = get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail=f"Workflow execution '{execution_id}' not found.")
    return _to_response(execution)


@router.patch("/{execution_id}", response_model=WorkflowExecutionResponse)
async def update_workflow(
    execution_id: str,
    body: WorkflowUpdateRequest,
    x_user: str = Header("anonymous"),
):
    rid = new_request_id()
    user = sanitize(x_user)
    execution = get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail=f"Workflow execution '{execution_id}' not found.")
    try:
        steps_raw = [s.model_dump() for s in body.steps] if body.steps is not None else None
        update_execution(
            execution_id=execution_id,
            status=body.status,
            steps=steps_raw,
            result=body.result,
            error=body.error,
        )
        updated = get_execution(execution_id)
        log(request_id=rid, user=user, action="workflow_update", status="ok",
            input_text=f"execution_id={execution_id} status={body.status}", jira_key=execution_id)
        return _to_response(updated)
    except Exception as e:
        log(request_id=rid, user=user, action="workflow_update", status="error",
            input_text=f"execution_id={execution_id}", error=sanitize(str(e)))
        raise HTTPException(status_code=500, detail=sanitize(str(e)))
