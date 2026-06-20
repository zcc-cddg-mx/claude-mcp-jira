import asyncio
import os

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
                },
                "required": ["query"],
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

    # Security checks
    try:
        verify_api_key(api_key)
        verify_ip(client_ip)
        check_permission(api_key, name)
        rate_check(api_key or "anonymous")
    except PermissionError as e:
        return [TextContent(type="text", text=f"Access denied: {e}")]
    except RuntimeError as e:
        return [TextContent(type="text", text=f"Rate limit: {e}")]

    # Pre-validation
    text = arguments.get("text", "") or arguments.get("query", "")
    if text and len(text) > _MAX_PAYLOAD_SIZE:
        return [TextContent(type="text", text=f"Error: input exceeds {_MAX_PAYLOAD_SIZE} characters")]
    if text and not text.strip():
        return [TextContent(type="text", text="Error: empty input")]

    # Dispatch — delegate everything to service layer
    try:
        if name == "create_jira_issue":
            result = service_client.create_issue(arguments["text"], user)
        elif name == "update_jira_issue":
            result = service_client.update_issue(arguments["key"], arguments["text"], user)
        elif name == "get_jira_issue":
            result = service_client.get_issue(arguments["key"], user)
        elif name == "search_jira_issues":
            result = service_client.search_issues(arguments["query"], user)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]

    import json
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


def _make_app() -> Starlette:
    transport = SseServerTransport("/messages")

    async def handle_sse(request: Request):
        api_key = request.headers.get("x-api-key")
        client_ip = request.client.host if request.client else None
        async with transport.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(
                streams[0],
                streams[1],
                server.create_initialization_options(),
            )

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
    uvicorn.run("mcp.server:app", host="0.0.0.0", port=port, reload=False)
