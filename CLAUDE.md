# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This repository is a **Claude MCP server that integrates with Jira**, enabling natural language ticket management from the CLI. It is currently in the planning/design phase — no implementation code exists yet.

The architectural design is documented in `arch/general.md` (in Spanish).

## Planned Architecture

Three-layer design — keep Claude, the service layer, and Jira as separate concerns:

```
[CLI] → [Service Layer (FastAPI)] → [Claude API]
                                  → [Jira REST API]
```

- **CLI**: Python (Typer) or Node.js (Commander.js) entry point that parses commands and dispatches to the service layer.
- **Service Layer (FastAPI)**: Validates inputs, maps natural language → Jira JSON schema, handles auth, and logs operations. This is the integration hub — Claude and Jira are never called directly from the CLI.
- **Claude API**: Acts as NLP engine — converts free text to structured Jira payloads, classifies intent (bug/task/story), generates descriptions, and suggests priorities.
- **Jira REST API**: Executes the actual operations (`/rest/api/3/issue`, `/rest/api/3/search`, `/rest/api/3/transition`).

**Key design constraint**: Claude must not call Jira directly. All Jira calls go through the service layer for validation, auditing, and rate limiting.

## Key Patterns

- **NL → Structured JSON**: Claude converts free-text to a validated Jira issue payload.
- **Action Dispatcher**: Intent classification gates which Jira operation runs (`create_issue`, `update_issue`, etc.).
- **Prompt Templates**: Reusable system prompts instruct Claude to output schema-conformant JSON.

## Intended CLI UX

```bash
claude-jira create "bug login en producción prioridad alta"
claude-jira update PROJ-123 "agregar logs de autenticación"
claude-jira summarize PROJ-123
claude-jira list "mis tickets abiertos"
```

## Setup

```bash
conda env create -f environment.yml
conda activate claude-mcp-jira
cp .env.example .env  # completar con credenciales reales
```

## Auth

- Jira Cloud: API Token + Basic Auth (`email:api_token`)
- Jira Enterprise: OAuth 2.0
- All credentials via environment variables — never hardcoded or passed as CLI args.
