from typing import Optional

from pydantic import BaseModel, Field

_PRIORITY_PATTERN = "^(Highest|High|Medium|Low|Lowest)$"
_ISSUE_TYPE_PATTERN = "^(Bug|Task|Story|Improvement)$"


class CreateIssueRequest(BaseModel):
    text: str = Field(..., min_length=5, max_length=2000)


class JiraIssuePayload(BaseModel):
    summary: str = Field(..., max_length=100)
    description: str
    priority: str = Field(..., pattern=_PRIORITY_PATTERN)
    issueType: str = Field(..., pattern=_ISSUE_TYPE_PATTERN)


class CreateIssueResponse(BaseModel):
    key: str
    summary: str
    issueType: str
    priority: str


class UpdateIssueRequest(BaseModel):
    text: str = Field(..., min_length=5, max_length=2000)


class UpdateIssuePayload(BaseModel):
    summary: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    priority: Optional[str] = Field(None, pattern=_PRIORITY_PATTERN)
    comment: Optional[str] = None


class UpdateIssueResponse(BaseModel):
    key: str
    status: str


class SummarizeIssueResponse(BaseModel):
    key: str
    summary: str


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)


class SearchQueryStruct(BaseModel):
    assignee: Optional[str] = None
    status: Optional[str] = None
    issuetype: Optional[str] = None
    priority: Optional[str] = None
    date_range: Optional[str] = Field(None, pattern="^(today|last_week|last_month)$")
    text_search: Optional[str] = None


class IssueResult(BaseModel):
    key: str
    summary: str
    status: str
    priority: str
    assignee: Optional[str] = None


class SearchResponse(BaseModel):
    total: int
    issues: list[IssueResult]


class TransitionIssueRequest(BaseModel):
    text: str = Field(..., min_length=3, max_length=2000)


class TransitionPayload(BaseModel):
    transition_id: str
    transition_name: str


class TransitionIssueResponse(BaseModel):
    key: str
    status: str
    transition: str


class LogWorkRequest(BaseModel):
    text: str = Field(..., min_length=3, max_length=2000)


class LogWorkPayload(BaseModel):
    time_spent_seconds: int = Field(..., gt=0)
    comment: Optional[str] = None
    started: Optional[str] = None


class LogWorkResponse(BaseModel):
    key: str
    time_spent_seconds: int
    comment: Optional[str] = None
