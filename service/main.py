from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from .routes import issues_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="claude-mcp-jira service",
    description="Service layer between CLI and Claude/Jira APIs",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(issues_router)


@app.get("/health")
def health():
    return {"status": "ok"}
