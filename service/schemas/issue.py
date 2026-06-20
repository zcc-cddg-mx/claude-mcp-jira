from pydantic import BaseModel, Field


class CreateIssueRequest(BaseModel):
    text: str = Field(..., min_length=5, max_length=2000)


class JiraIssuePayload(BaseModel):
    summary: str = Field(..., max_length=100)
    description: str
    priority: str = Field(..., pattern="^(Highest|High|Medium|Low|Lowest)$")
    issueType: str = Field(..., pattern="^(Bug|Task|Story|Improvement)$")


class CreateIssueResponse(BaseModel):
    key: str
    summary: str
    issueType: str
    priority: str
