import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from .routes import actions_router, assign_router, clone_router, comments_router, issues_router, labels_router, link_meta_router, link_router, priority_router, search_router, summarize_router, transitions_router, update_router, worklog_router

_ENV = os.environ.get("APP_ENV", "dev").lower()
_docs_url = "/docs" if _ENV == "dev" else None
_redoc_url = "/redoc" if _ENV == "dev" else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="claude-mcp-jira service",
    description="Service layer between CLI and Claude/Jira APIs",
    version="0.3.0",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
)

app.include_router(actions_router)
app.include_router(assign_router)
app.include_router(clone_router)
app.include_router(comments_router)
app.include_router(issues_router)
app.include_router(labels_router)
app.include_router(link_meta_router)
app.include_router(link_router)
app.include_router(priority_router)
app.include_router(update_router)
app.include_router(summarize_router)
app.include_router(search_router)
app.include_router(transitions_router)
app.include_router(worklog_router)


@app.get("/health")
def health():
    return {"status": "ok"}
