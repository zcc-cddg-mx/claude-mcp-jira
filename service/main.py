import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from .routes import actions_router, assign_router, clone_router, comments_router, git_repos_router, git_sync_router, issues_router, labels_router, link_meta_router, link_router, priority_router, projects_router, saz_router, search_router, summarize_router, transitions_router, update_router, worklog_router
from .clients.project_db import init_db, seed
from .git.repo_registry import init_repo_registry

_ENV = os.environ.get("APP_ENV", "dev").lower()
_docs_url = "/docs" if _ENV == "dev" else None
_redoc_url = "/redoc" if _ENV == "dev" else None

# Known projects with hand-curated constraints (from docs/jira-fields.md).
# Auto-discovery fills in the rest when users first access other projects.
_SEED_PROJECTS = {
    "ZNRX": {
        "priority_format": "id",
        "priority_ids": {"Highest": "1", "High": "2", "Low": "4"},
        "required_custom": {"customfield_25832": {"id": "44461"}},
        "issuetype_fallback": {"Bug": "Task", "Improvement": "Task"},
        "ticket_lang": "es",
    },
    "AIPROJECTS": {
        "priority_format": "name",
        "priority_ids": {},
        "required_custom": {},
        "issuetype_fallback": {},
        "ticket_lang": "en",
    },
    "SCRX": {
        "priority_format": "name",
        "priority_ids": {},
        "required_custom": {},
        "issuetype_fallback": {},
        "ticket_lang": "es",
    },
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_repo_registry()
    for key, cfg in _SEED_PROJECTS.items():
        seed(key, cfg)
    yield


app = FastAPI(
    title="claude-mcp-jira service",
    description="Service layer between CLI and Claude/Jira APIs",
    version="0.4.0",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
)

app.include_router(actions_router)
app.include_router(git_repos_router)
app.include_router(git_sync_router)
app.include_router(assign_router)
app.include_router(clone_router)
app.include_router(comments_router)
app.include_router(issues_router)
app.include_router(labels_router)
app.include_router(link_meta_router)
app.include_router(link_router)
app.include_router(priority_router)
app.include_router(projects_router)
app.include_router(saz_router)
app.include_router(update_router)
app.include_router(summarize_router)
app.include_router(search_router)
app.include_router(transitions_router)
app.include_router(worklog_router)


@app.get("/health")
def health():
    return {"status": "ok"}
