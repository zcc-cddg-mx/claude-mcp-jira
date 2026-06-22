from typing import Optional
from pydantic import BaseModel, Field


class GitSyncRequest(BaseModel):
    repo_path: str = Field(..., min_length=1, max_length=500, example="/home/user/repos/auth-service")
    since_days: int = Field(1, ge=1, le=30, example=1)
    dry_run: bool = Field(True, description="If true, returns preview only — does not register worklogs in Jira")
    author: Optional[str] = Field(None, min_length=1, max_length=200, description="Filter commits by author email")


class GitSessionResult(BaseModel):
    issue_key: Optional[str] = None
    estimated_hours: float
    estimated_seconds: int
    confidence: str
    messages: list[str]
    total_loc: int
    commit_count: int
    worklog_registered: bool = False


class GitSyncResponse(BaseModel):
    repo_path: str
    since_days: int
    dry_run: bool
    branch: Optional[str] = None
    total_commits: int
    sessions: list[GitSessionResult]
    sessions_with_key: int
    sessions_without_key: int
    worklogs_registered: int
