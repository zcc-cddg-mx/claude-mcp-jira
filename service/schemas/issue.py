from typing import Optional

from pydantic import BaseModel, Field

_PRIORITY_PATTERN = "^(Highest|High|Medium|Low|Lowest)$"
_ISSUE_TYPE_PATTERN = "^(Bug|Task|Story|Improvement)$"


class CreateIssueRequest(BaseModel):
    text: str = Field(..., min_length=5, max_length=2000, example="bug en el login de producción, prioridad alta")
    project: Optional[str] = Field(None, min_length=2, max_length=20, example="AIPROJECTS")


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
    text: str = Field(..., min_length=5, max_length=2000, example="cambiar prioridad a crítica y añadir comentario de seguimiento")


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
    query: str = Field(..., min_length=3, max_length=500, example="mis bugs abiertos de esta semana")
    project: Optional[str] = Field(None, min_length=2, max_length=20, example="AIPROJECTS")


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
    text: str = Field(..., min_length=3, max_length=2000, example="pasar a en progreso")


class TransitionPayload(BaseModel):
    transition_id: str
    transition_name: str


class TransitionIssueResponse(BaseModel):
    key: str
    status: str
    transition: str


class LogWorkRequest(BaseModel):
    text: str = Field(..., min_length=3, max_length=2000, example="2 horas revisando la arquitectura del módulo de autenticación")


class LogWorkPayload(BaseModel):
    time_spent_seconds: int = Field(..., ge=60)
    comment: Optional[str] = None
    started: Optional[str] = None


class LogWorkResponse(BaseModel):
    key: str
    time_spent_seconds: int
    comment: Optional[str] = None


class AddCommentRequest(BaseModel):
    text: str = Field(..., min_length=3, max_length=2000, example="se identificó la causa raíz: falta validación en el token de sesión")


class AddCommentPayload(BaseModel):
    comment: str


class AddCommentResponse(BaseModel):
    key: str
    comment: str


class AssignIssueRequest(BaseModel):
    text: str = Field(..., min_length=3, max_length=2000, example="asigna a carlos.duarte")


class AssignIssuePayload(BaseModel):
    assignee: Optional[str] = Field(None, min_length=1)


class AssignIssueResponse(BaseModel):
    key: str
    assignee: Optional[str] = None


class SetPriorityRequest(BaseModel):
    text: str = Field(..., min_length=3, max_length=2000, example="subir prioridad a alta")


class SetPriorityPayload(BaseModel):
    priority: str = Field(..., pattern=_PRIORITY_PATTERN)


class SetPriorityResponse(BaseModel):
    key: str
    priority: str


class CloneIssueRequest(BaseModel):
    text: str = Field("", max_length=2000, example="clonar con título: revisión mensual de julio 2026")


class CloneIssuePayload(BaseModel):
    summary: Optional[str] = None
    description: Optional[str] = None


class CloneIssueResponse(BaseModel):
    source_key: str
    new_key: str
    summary: str


class LinkIssueRequest(BaseModel):
    text: str = Field(..., min_length=5, max_length=2000, example="relacionar con ZNRX-68147, la 68128 depende de la 68147")


class LinkTypeItem(BaseModel):
    id: str
    name: str
    outward: str
    inward: str


class LinkIssuePayload(BaseModel):
    target_key: str
    link_type_name: str
    source_is_outward: bool


class LinkIssueResponse(BaseModel):
    source_key: str
    target_key: str
    link_type_name: str


class ActionsRequest(BaseModel):
    text: str = Field(..., min_length=3, max_length=2000, example="pon los labels: backend, api")


class LabelsPayload(BaseModel):
    operation: str
    labels: list[str]


class ActionsResponse(BaseModel):
    key: str
    action: str
    labels: list[str]


class LabelsRequest(BaseModel):
    text: str = Field(..., min_length=3, max_length=2000, example="pon los labels: backend, api")


class LabelsResponse(BaseModel):
    key: str
    operation: str
    labels: list[str]


class CreateSAZRequest(BaseModel):
    text: str = Field(..., min_length=5, max_length=2000, example="solicitar reinicio del servicio de autenticación en producción")
    znrx_key: Optional[str] = Field(None, pattern=r'^[A-Z][A-Z0-9]+-\d+$', example="ZNRX-68126")


class CreateDeploymentSAZRequest(BaseModel):
    repo: str = Field(..., min_length=1, max_length=200, example="ov-arizona-backend-ecuador")
    target: str = Field(..., min_length=1, max_length=50, example="test")
    branch: str = Field(..., min_length=1, max_length=255, example="feature/ZNRX-68248-workflow")
    base_branch: str = Field(..., min_length=1, max_length=255, example="develop")
    pr_id: int = Field(..., example=2505)
    pr_url: str = Field(..., min_length=10, max_length=500, example="https://dev.azure.com/ZurichInsurance-EC/...")
    project_label: str = Field("OV", max_length=50, example="OV")
    znrx_key: Optional[str] = Field(None, pattern=r'^[A-Z][A-Z0-9]+-\d+$', example="ZNRX-68248")


class SAZIssuePayload(BaseModel):
    summary: str = Field(..., max_length=255)
    description: str
    issue_type: str = Field(..., pattern="^(Support|Incident|Nueva Iniciativa)$")


class CreateSAZResponse(BaseModel):
    saz_key: str
    znrx_key: Optional[str] = None
    summary: str
    status: str
