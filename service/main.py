from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from .routes import issues_router, search_router, summarize_router, transitions_router, update_router, worklog_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="claude-mcp-jira service",
    description="Service layer between CLI and Claude/Jira APIs",
    version="0.3.0",
    lifespan=lifespan,
)

app.include_router(issues_router)
app.include_router(update_router)
app.include_router(summarize_router)
app.include_router(search_router)
app.include_router(transitions_router)
app.include_router(worklog_router)


@app.get("/health")
def health():
    return {"status": "ok"}
