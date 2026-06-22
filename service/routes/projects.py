from fastapi import APIRouter, Header, HTTPException

from ..clients.project_db import get_or_discover, list_projects
from ..clients.rate_limiter import check as rate_limit_check
from ..clients.sanitizer import sanitize

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_projects_endpoint(x_user: str = Header(default="anonymous")):
    """List all registered projects with their discovered config."""
    try:
        rate_limit_check(x_user)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))
    return {"projects": list_projects()}


@router.get("/{key}")
def get_project_endpoint(key: str, x_user: str = Header(default="anonymous")):
    """Get config for a single project. Triggers auto-discovery if not registered."""
    try:
        rate_limit_check(x_user)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))
    try:
        cfg = get_or_discover(key.upper())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=sanitize(str(e)))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Jira request failed: {sanitize(str(e))}")
    return {"project_key": key.upper(), **cfg}
