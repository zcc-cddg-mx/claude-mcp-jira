# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This repository implements a **Claude MCP server that integrates with Jira**, enabling natural language ticket management from the CLI. Target environment: Zurich corporate network with `jira.zurich.com` (Jira Server/Data Center).

Architecture and implementation decisions are documented in `arch/` (in Spanish).

## Architecture

Three-layer design — CLI never calls Claude or Jira directly:

```
[CLI (Typer)] → [Service Layer (FastAPI)] → [Claude API (LiteLLM proxy)]
                                          → [Jira REST API v2 — jira.zurich.com]
```

**Key constraints for Zurich environment:**
- Jira is Server/Data Center, not Cloud → REST API v2, PAT Bearer auth, plain-text descriptions
- Claude API goes through the internal LiteLLM proxy (see parent repo `CLAUDE.md` for env vars)
- Corporate firewall requires `REQUESTS_CA_BUNDLE` pointing to `certs/` for Jira calls
- No external services (Atlassian MCP cloud, N8N, Zapier) — all traffic stays inside the network

## Setup

```bash
conda env create -f environment.yml
conda activate claude-mcp-jira
cp .env.example .env  # fill in JIRA_PAT and uncomment REQUESTS_CA_BUNDLE
```

## Running

```bash
# Fase 1 — direct CLI (prototype only)
python cli/main.py create "bug login en producción prioridad alta"

# Fase 2+ — via service layer
docker compose up
python cli/main.py create "bug login en producción prioridad alta"
```

## Jira Auth (Server/DC)

Generate a PAT at `jira.zurich.com` → Profile → Personal Access Tokens. Set it as `JIRA_PAT` in `.env`. The client sends `Authorization: Bearer <PAT>` on every request.

## Corporate certificates

`certs/` contains the Zurich root CA files. Set `REQUESTS_CA_BUNDLE` in `.env` to the appropriate cert for your endpoint:

- `certs/zurichseguros-rootca-until-2031_03_20.crt` — standard internal services
- `certs/cacert-workflow-uat.pem` — UAT workflow endpoints
- `certs/localCA.crt` — local dev CA

## Implementation phases

See `arch/implementation-plan.md` for the full plan. Current state:

| Fase | Estado | Descripción |
|---|---|---|
| 1 — Prototipo CLI | ✅ Completa | `cli/main.py` — comando `create` |
| 2 — Service Layer | Pendiente | FastAPI + sanitize + audit log |
| 3 — Comandos completos | Pendiente | `update`, `summarize`, `list` |
| 4 — MCP Server | Pendiente | Servicio Docker deployable internamente |
