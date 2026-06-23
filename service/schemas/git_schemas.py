from typing import Optional
from pydantic import BaseModel, Field


class GitSyncRequest(BaseModel):
    repo_path: Optional[str] = Field(None, min_length=1, max_length=500, example="/home/user/repos/auth-service")
    repo_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Registered repo alias (resolves path and defaults from registry)")
    since_days: int = Field(1, ge=1, le=30, example=1)
    dry_run: bool = Field(True, description="If true, returns preview only — does not register worklogs in Jira")
    author: Optional[str] = Field(None, min_length=1, max_length=200, description="Filter commits by author email")


class GitRepoCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, example="auth-service")
    repo_path: str = Field(..., min_length=1, max_length=500, example="/home/user/repos/auth-service")
    jira_project: Optional[str] = Field(None, min_length=1, max_length=20, description="Default Jira project key")
    default_issue_key: Optional[str] = Field(None, min_length=3, max_length=30, description="Default ticket for worklog when no key detected")
    is_default: bool = Field(False, description="Mark this repo as the default for git sync")
    origin: Optional[str] = Field(None, min_length=1, max_length=500, description="Remote origin URL (auto-detected if omitted)")


class GitRepoEntry(BaseModel):
    name: str
    repo_path: str
    origin: Optional[str] = None
    jira_project: Optional[str] = None
    default_issue_key: Optional[str] = None
    is_default: bool = False
    created_at: str


class GitRepoListResponse(BaseModel):
    repos: list[GitRepoEntry]
    total: int


class GitSessionResult(BaseModel):
    issue_key: Optional[str] = None
    estimated_hours: float        # final estimate (humanizer-adjusted if enabled)
    estimated_seconds: int        # final estimate in seconds
    base_estimated_hours: Optional[float] = None  # algorithmic estimate before humanizer
    confidence: str
    messages: list[str]
    total_loc: int
    commit_count: int
    worklog_registered: bool = False
    humanizer_reason: Optional[str] = None


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
