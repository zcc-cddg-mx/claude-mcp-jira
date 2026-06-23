import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import TextContent, Tool
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route

load_dotenv()

from .auth import verify_api_key, verify_ip
from .rbac import check_permission
from .rate_limiter import check as rate_check
from . import service_client

_logger = logging.getLogger("jira_mcp.audit")
_AUDIT_LOG_PATH = os.environ.get("AUDIT_LOG_PATH", "audit.log")


def _audit(*, request_id: str, user: str, tool: str, status: str, error: str | None = None) -> None:
    entry = {
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "layer": "mcp",
        "user": user,
        "tool": tool,
        "status": status,
        "error": error,
    }
    try:
        with open(_AUDIT_LOG_PATH, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        _logger.warning("mcp audit write failed: %s", _AUDIT_LOG_PATH)

server = Server("claude-mcp-jira")

_MAX_PAYLOAD_SIZE = int(os.environ.get("MCP_MAX_PAYLOAD_SIZE", "2000"))
_MAX_RESULTS_HINT = int(os.environ.get("JIRA_MAX_RESULTS", "50"))


def _make_tools() -> list[Tool]:
    max_len = _MAX_PAYLOAD_SIZE
    search_max = min(500, max_len)
    return [
        Tool(
            name="create_jira_issue",
            description="Create a Jira ticket from a plain-text description.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Natural language description of the issue to create",
                        "maxLength": max_len,
                    },
                    "project": {
                        "type": "string",
                        "description": "Optional Jira project key (e.g. ZNRX, AIPROJECTS, SCRX). Defaults to the configured default project.",
                    },
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="update_jira_issue",
            description="Update an existing Jira ticket using a plain-text instruction.",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Jira issue key (e.g. PROJ-123)"},
                    "text": {
                        "type": "string",
                        "description": "Natural language instruction of what to change",
                        "maxLength": max_len,
                    },
                },
                "required": ["key", "text"],
            },
        ),
        Tool(
            name="get_jira_issue",
            description="Get a plain-text summary of a Jira ticket.",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Jira issue key (e.g. PROJ-123)"},
                },
                "required": ["key"],
            },
        ),
        Tool(
            name="search_jira_issues",
            description=f"Search Jira issues using a natural language query. Returns up to {_MAX_RESULTS_HINT} results.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query",
                        "maxLength": search_max,
                    },
                    "project": {
                        "type": "string",
                        "description": "Optional Jira project key to scope the search (e.g. ZNRX, AIPROJECTS, SCRX).",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="assign_jira_issue",
            description="Assign a Jira ticket to a user using a plain-text instruction.",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Jira issue key (e.g. PROJ-123)"},
                    "text": {
                        "type": "string",
                        "description": "Natural language instruction for assignment (e.g. 'assign to carlos.duarte' or 'unassign')",
                        "maxLength": max_len,
                    },
                },
                "required": ["key", "text"],
            },
        ),
        Tool(
            name="set_priority_jira_issue",
            description="Change the priority of a Jira ticket using a plain-text instruction.",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Jira issue key (e.g. PROJ-123)"},
                    "text": {
                        "type": "string",
                        "description": "Natural language instruction for priority (e.g. 'set priority to high')",
                        "maxLength": max_len,
                    },
                },
                "required": ["key", "text"],
            },
        ),
        Tool(
            name="add_comment_jira_issue",
            description="Add a comment to an existing Jira ticket from a plain-text description.",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Jira issue key (e.g. PROJ-123)"},
                    "text": {
                        "type": "string",
                        "description": "Natural language description of the comment to add",
                        "maxLength": max_len,
                    },
                },
                "required": ["key", "text"],
            },
        ),
        Tool(
            name="link_jira_issues",
            description="Link two Jira tickets expressing a dependency or relationship (blocks, relates, depends on, duplicates, etc.).",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Jira issue key of the source ticket (e.g. PROJ-123)"},
                    "text": {
                        "type": "string",
                        "description": "Natural language description of the link (e.g. 'link with ZNRX-456, this ticket depends on it')",
                        "maxLength": max_len,
                    },
                },
                "required": ["key", "text"],
            },
        ),
        Tool(
            name="sync_git_worklogs",
            description="Read a local Git repository, detect work sessions linked to Jira tickets (by commit message or branch name), and optionally register worklogs. Always runs as dry_run=true first to show a preview — set dry_run=false to actually register.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Absolute path to the local Git repository (e.g. /home/user/repos/auth-service). Mutually exclusive with repo_name.",
                    },
                    "repo_name": {
                        "type": "string",
                        "description": "Registered repo alias (e.g. 'auth-service'). Resolves path and defaults from registry. Mutually exclusive with repo_path.",
                    },
                    "since_days": {
                        "type": "integer",
                        "description": "How many days back to scan commits (default: 1)",
                        "default": 1,
                        "minimum": 1,
                        "maximum": 30,
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true (default), returns a preview only — no worklogs are registered in Jira. Set to false to register.",
                        "default": True,
                    },
                    "author": {
                        "type": "string",
                        "description": "Optional: filter commits by author email (e.g. carlos.duarte2@mx.zurich.com)",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="register_git_repo",
            description="Register a local Git repository in the repo registry, associating it with a Jira project and optional default ticket. Registered repos can be referenced by name in sync_git_worklogs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Short alias for the repo (e.g. 'auth-service')",
                        "maxLength": 100,
                    },
                    "repo_path": {
                        "type": "string",
                        "description": "Absolute path to the local Git repository (e.g. /home/user/repos/auth-service)",
                        "maxLength": 500,
                    },
                    "jira_project": {
                        "type": "string",
                        "description": "Default Jira project key for this repo (e.g. ZNRX, AIPROJECTS)",
                    },
                    "default_issue_key": {
                        "type": "string",
                        "description": "Default Jira ticket to log work against when no issue key is found in commits (e.g. ZNRX-100)",
                    },
                    "is_default": {
                        "type": "boolean",
                        "description": "Set as the default repo for git sync when no repo_path or repo_name is given",
                        "default": False,
                    },
                },
                "required": ["name", "repo_path"],
            },
        ),
        Tool(
            name="list_git_repos",
            description="List all registered Git repositories in the repo registry.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="create_saz_request",
            description="Create a SAZ ticket (Solicitud Release Zurich) for DevOps/Release team requests: service restarts, deployments, Git repo management, infrastructure access, environment promotions. Optionally link to a ZNRX ticket.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Natural language description of the DevOps/Release request",
                        "maxLength": max_len,
                    },
                    "znrx_key": {
                        "type": "string",
                        "description": "Optional ZNRX issue key to link the SAZ to (e.g. ZNRX-68126)",
                    },
                },
                "required": ["text"],
            },
        ),
    ]


_TOOLS = _make_tools()


@server.list_tools()
async def list_tools() -> list[Tool]:
    return _TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    api_key = arguments.pop("_api_key", None)
    client_ip = arguments.pop("_client_ip", None)
    user = arguments.pop("_user", api_key or "mcp-anonymous")

    rid = str(uuid.uuid4())

    # Security checks
    try:
        verify_api_key(api_key)
        verify_ip(client_ip)
        check_permission(api_key, name)
        rate_check(api_key or "anonymous")
    except PermissionError as e:
        _audit(request_id=rid, user=user, tool=name, status="denied", error=str(e))
        return [TextContent(type="text", text=f"Access denied: {e}")]
    except RuntimeError as e:
        _audit(request_id=rid, user=user, tool=name, status="rate_limited", error=str(e))
        return [TextContent(type="text", text=f"Rate limit: {e}")]

    # Pre-validation
    text = arguments.get("text", "") or arguments.get("query", "")
    if text and len(text) > _MAX_PAYLOAD_SIZE:
        _audit(request_id=rid, user=user, tool=name, status="rejected", error="payload_too_large")
        return [TextContent(type="text", text=f"Error: input exceeds {_MAX_PAYLOAD_SIZE} characters")]
    if text and not text.strip():
        _audit(request_id=rid, user=user, tool=name, status="rejected", error="empty_input")
        return [TextContent(type="text", text="Error: empty input")]

    # Dispatch — delegate everything to service layer
    try:
        if name == "create_jira_issue":
            result = service_client.create_issue(arguments["text"], user, arguments.get("project"))
        elif name == "update_jira_issue":
            result = service_client.update_issue(arguments["key"], arguments["text"], user)
        elif name == "get_jira_issue":
            result = service_client.get_issue(arguments["key"], user)
        elif name == "search_jira_issues":
            result = service_client.search_issues(arguments["query"], user, arguments.get("project"))
        elif name == "assign_jira_issue":
            result = service_client.assign_issue(arguments["key"], arguments["text"], user)
        elif name == "set_priority_jira_issue":
            result = service_client.set_priority(arguments["key"], arguments["text"], user)
        elif name == "add_comment_jira_issue":
            result = service_client.add_comment(arguments["key"], arguments["text"], user)
        elif name == "link_jira_issues":
            result = service_client.link_issues(arguments["key"], arguments["text"], user)
        elif name == "register_git_repo":
            result = service_client.register_git_repo(
                name=arguments["name"],
                repo_path=arguments["repo_path"],
                user=user,
                jira_project=arguments.get("jira_project"),
                default_issue_key=arguments.get("default_issue_key"),
                is_default=arguments.get("is_default", False),
            )
        elif name == "list_git_repos":
            result = service_client.list_git_repos(user=user)
        elif name == "create_saz_request":
            result = service_client.create_saz(arguments["text"], arguments.get("znrx_key"), user)
        elif name == "sync_git_worklogs":
            result = service_client.sync_git_worklogs(
                repo_path=arguments.get("repo_path"),
                repo_name=arguments.get("repo_name"),
                user=user,
                since_days=arguments.get("since_days", 1),
                dry_run=arguments.get("dry_run", True),
                author=arguments.get("author"),
            )
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        _audit(request_id=rid, user=user, tool=name, status="error", error=str(e))
        return [TextContent(type="text", text=f"Error: {e}")]

    _audit(request_id=rid, user=user, tool=name, status="ok")
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


_SSE_TIMEOUT = int(os.environ.get("MCP_SSE_TIMEOUT", "300"))


def _make_app() -> Starlette:
    transport = SseServerTransport("/messages")

    async def handle_sse(request: Request):
        api_key = request.headers.get("x-api-key")
        client_ip = request.client.host if request.client else None
        async with transport.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            try:
                await asyncio.wait_for(
                    server.run(
                        streams[0],
                        streams[1],
                        server.create_initialization_options(),
                    ),
                    timeout=_SSE_TIMEOUT,
                )
            except asyncio.TimeoutError:
                _logger.warning("SSE session timed out after %ss", _SSE_TIMEOUT)

    async def handle_messages(request: Request):
        await transport.handle_post_message(request.scope, request.receive, request._send)

    return Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages", app=transport.handle_post_message),
        ]
    )


app = _make_app()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("MCP_PORT", "8001"))
    uvicorn.run("jira_mcp.server:app", host="0.0.0.0", port=port, reload=False)
