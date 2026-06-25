from typing import Optional
from pydantic import BaseModel, Field


class CreateFeaturePRRequest(BaseModel):
    issue_key: str = Field(..., pattern=r"^[A-Z]+-\d+$", example="ZNRX-123")
    repo: str = Field(..., min_length=1, max_length=200, example="ov-arizona-backend-ecuador")
    repo_path: str = Field(..., min_length=1, max_length=500, example="/repos/ov-arizona-backend-ecuador")
    target: str = Field("developer", min_length=1, max_length=100)
    commit_message: str = Field(..., min_length=1, max_length=500)
    files: list[str] = Field(default=[], description="Files to commit. Empty → auto-detect via preview.")


class WorkflowStepStatus(BaseModel):
    name: str
    status: str
    detail: Optional[str] = None


class WorkflowExecutionResponse(BaseModel):
    execution_id: str
    workflow_type: str
    issue_key: str
    status: str
    steps: list[WorkflowStepStatus]
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str


class WorkflowUpdateRequest(BaseModel):
    status: Optional[str] = None
    steps: Optional[list[WorkflowStepStatus]] = None
    result: Optional[dict] = None
    error: Optional[str] = None
