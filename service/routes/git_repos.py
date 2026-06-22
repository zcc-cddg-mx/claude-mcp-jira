import logging
import os

from fastapi import APIRouter, HTTPException

from ..audit import log, new_request_id
from ..clients.sanitizer import sanitize
from ..schemas.git_schemas import GitRepoCreateRequest, GitRepoEntry, GitRepoListResponse
from ..git.repo_registry import (
    delete_repo,
    get_repo,
    init_repo_registry,
    infer_name_from_path,
    list_repos,
    register_repo,
)

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/git/repos", tags=["git"])


@router.post("", response_model=GitRepoEntry, status_code=201)
async def register_repo_endpoint(body: GitRepoCreateRequest):
    rid = new_request_id()

    if not os.path.isabs(body.repo_path):
        raise HTTPException(status_code=422, detail="repo_path debe ser una ruta absoluta.")

    try:
        entry = register_repo(
            name=body.name,
            repo_path=body.repo_path,
            jira_project=body.jira_project,
            default_issue_key=body.default_issue_key,
            is_default=body.is_default,
            origin=body.origin,
        )
    except Exception as e:
        log(request_id=rid, user="system", action="git_repo_register",
            input_text=sanitize(body.name), status="error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error registrando repo: {sanitize(str(e))}")

    log(request_id=rid, user="system", action="git_repo_register",
        input_text=sanitize(body.name), status="ok")
    return GitRepoEntry(**entry)


@router.get("", response_model=GitRepoListResponse)
async def list_repos_endpoint():
    repos = list_repos()
    return GitRepoListResponse(repos=[GitRepoEntry(**r) for r in repos], total=len(repos))


@router.get("/{name}", response_model=GitRepoEntry)
async def get_repo_endpoint(name: str):
    entry = get_repo(name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Repo '{name}' no encontrado.")
    return GitRepoEntry(**entry)


@router.delete("/{name}", status_code=204)
async def delete_repo_endpoint(name: str):
    rid = new_request_id()
    deleted = delete_repo(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Repo '{name}' no encontrado.")
    log(request_id=rid, user="system", action="git_repo_delete",
        input_text=sanitize(name), status="ok")
