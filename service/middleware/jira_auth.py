from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from ..clients.jira_client import _request_pat


class JiraAuthMiddleware(BaseHTTPMiddleware):
    """Extract X-Jira-Token header and inject it into the per-request ContextVar.

    If present, all Jira calls in that request use this PAT instead of the
    service-account PAT from .env. If absent, falls back to JIRA_PAT (env).
    The token value is never logged — only its source is recorded in audit entries.
    """

    async def dispatch(self, request: Request, call_next):
        token = request.headers.get("X-Jira-Token")
        if token:
            tok = _request_pat.set(token)
            try:
                return await call_next(request)
            finally:
                _request_pat.reset(tok)
        return await call_next(request)
