from fastapi import APIRouter, HTTPException

from ..clients.project_db import get_or_discover, list_projects
from ..clients.sanitizer import sanitize

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_projects_endpoint():
    """List all registered projects with their discovered config."""
    return {"projects": list_projects()}


@router.get("/{key}")
def get_project_endpoint(key: str):
    """Get config for a single project. Triggers auto-discovery if not registered."""
    try:
        cfg = get_or_discover(key.upper())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=sanitize(str(e)))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Jira request failed: {sanitize(str(e))}")
    return {"project_key": key.upper(), **cfg}
