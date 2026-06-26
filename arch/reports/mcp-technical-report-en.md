# Technical Report: claude-mcp-jira
# Development Automation Agent — Zurich Insurance Ecuador

**Version**: 2.0  
**Date**: June 2026  
**Team**: Digital Development — Zurich Insurance Ecuador  
**Contact**: carlos.duarte2@mx.zurich.com

---

## Executive Summary

`claude-mcp-jira` is a **development lifecycle automation platform** built on the Zurich corporate network. It integrates Jira, Git, and Azure DevOps into a single natural-language-driven workflow from the IDE (Claude Code), eliminating repetitive manual tasks for the development team.

The system operates as a **specialized Ecuador Agent** — equivalent to Zurich Global AI's AGENT concept — with capabilities that go beyond basic Jira CRUD:

| Capability | Description | Available in et-ai-mcp-jira (global)? |
|---|---|---|
| Full Jira management | 9 tools: create, update, search, comment, link, assign, priority, SAZ | Partial (basic CRUD only) |
| **Git Intelligence** | Auto-detects work sessions from commits and logs worklogs to Jira | ❌ No |
| **Deployment SAZ workflow** | Azure DevOps PR → deployment SAZ ticket in a single command | ❌ No |
| **Workflow Orchestrator** | 6 orchestrated steps: commit → branch → PR → CI → Jira | ❌ No |
| **Azure DevOps EC** | Integration with tenant `ZurichInsurance-EC / Oficina-Virtual-ZEC` | ❌ No |

**Current state:** 19 MCP tools · 232 tests · end-to-end validation with real PRs and SAZ tickets · 100% Zurich internal network.

---

## 1. Context and Motivation

### Original Problem

The development team was manually handling:
- Creating and updating Jira tickets (ZNRX, SAZ, AIPROJECTS, SCRX)
- Submitting deployment requests to the DevOps team (manual SAZ tickets)
- Logging worked hours (inconsistent or missing worklogs)
- Coordinating branches, commits, and PRs in Azure DevOps

### Solution

An AI orchestration agent that executes these workflows from the CLI or Claude Code (IDE), always keeping a human in the loop for validation and adjustments.

### Zurich Network Constraints

The system respects all corporate restrictions:
- **Jira Server / Data Center** — `jira.zurich.com`; REST API v2; PAT Bearer auth; no Jira Cloud
- **Claude API** — routed through the internal LiteLLM proxy; no direct traffic to `api.anthropic.com`
- **Azure DevOps** — Ecuador tenant `ZurichInsurance-EC / Oficina-Virtual-ZEC`
- **Corporate certificates** — `certs/` directory with Zurich CA bundle for all TLS calls
- **No external cloud services** — no Atlassian MCP Cloud, N8N, Zapier

---

## 2. Architecture

### 2.1 Layer Diagram

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  USER INTERFACE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [Claude Code (IDE)]          [CLI (Typer)]
         │ SSE/MCP                   │ HTTP
         ▼                           ▼
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  MCP SERVER  :18001  (jira_mcp/)
  Auth: X-API-Key + IP allowlist + RBAC + rate limiting
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
         │ HTTP
         ▼
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SERVICE LAYER  :18000  (service/)
  Sanitization · Audit log · JQL builder · Project registry
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
         │                           │                    │
         ▼                           ▼                    ▼
  [LiteLLM proxy]          [jira.zurich.com]    [code-agent-mcp :5001]
  [→ Claude API]           [REST API v2]        [Git + Azure DevOps EC]
```

**Key principle:** the MCP server never calls Jira or Claude directly — all requests go through the service layer.

### 2.2 What is MCP?

The **Model Context Protocol (MCP)** is an open protocol by Anthropic that standardizes how LLMs connect to external services. It is the "universal interface" that allows Claude to invoke real tools safely and in an auditable way.

```
[Claude Code]  ←──MCP/SSE──►  [MCP Server]  ──HTTP──►  [Service Layer]  ──►  [Jira / Azure / Git]
```

The SSE (Server-Sent Events) transport keeps the MCP server entirely within the internal network — never on the user's machine or on any cloud service.

---

## 3. System Capabilities (19 MCP Tools)

### 3.1 Jira Management (9 tools)

| Tool | Min. Role | Description |
|---|---|---|
| `create_jira_issue` | dev | Creates a ticket from free text; NL → Jira fields |
| `update_jira_issue` | lead | Updates any field from free text |
| `get_jira_issue` | dev | Claude-generated summary of a ticket |
| `search_jira_issues` | dev | NL search → controlled JQL (max 50 results) |
| `add_comment_jira_issue` | dev | Adds a comment from free text |
| `link_jira_issues` | dev | Links two tickets (depends on, blocks, relates to…) |
| `assign_jira_issue` | lead | Assigns a ticket from free text |
| `set_priority_jira_issue` | lead | Changes priority from free text |
| `create_saz_request` | lead | Creates a SAZ ticket; optional `znrx_key` to link to a requirement |

### 3.2 Git Intelligence (3 tools)

Differential capability — no equivalent exists in the Zurich global ecosystem.

| Tool | Description |
|---|---|
| `register_git_repo` | Registers a local repo alias → path + Jira project |
| `list_git_repos` | Lists registered repos |
| `sync_git_worklogs` | Scans commits by author/period → detects work sessions → logs worklogs to Jira; `dry_run=true` by default; Claude humanizer adjusts estimates semantically |

**Typical flow:**
```
git log → detect sessions (time gap) → estimate time by LOC/type → Claude adjusts
(debugging = ×1.5, high complexity = ×1.3, late-night work = +15min) → POST /worklog to Jira
```

### 3.3 Azure DevOps / PR Lifecycle (4 tools)

Integration with the Ecuador tenant `ZurichInsurance-EC / Oficina-Virtual-ZEC`.

| Tool | Min. Role | Description |
|---|---|---|
| `run_code_agent` | lead | Queues an async git task: create branch + commit + push + auxiliary branch |
| `get_code_agent_status` | dev | Task status (queued/running/done/error + steps) |
| `create_azure_pull_request` | lead | Idempotent: ensure aux branch → create or return existing PR |
| `get_pull_request_status` | dev | PR status + CI build result |

### 3.4 Deployment SAZ Workflow (3 tools)

Full deployment flow in a single command.

| Tool | Min. Role | Description |
|---|---|---|
| `create_deployment_saz_workflow` | lead | Synchronous: lookup repo → Azure PR → SAZ ticket; `ticket` accepts Jira key or requirement ID |
| `update_pull_request_status` | lead | Changes PR status: `abandoned / completed / active` |
| `set_repo_branch_map` | lead | Configures `developer→developer`, `test→test`, `prod→develop` mapping per repo |

**Typical flow:**
```
create_deployment_saz_workflow(
  repo="ov-arizona-backend-ecuador",
  branch="feature/REQ2298577",
  target="test",
  ticket="REQ2298577"
)
→ PR #2575 created in Azure DevOps (feature/REQ2298577 → test)
→ SAZ-7442 created: "Despliegue ambiente TEST - OV - Limite Autos - Backend Ecuador"
```

### 3.5 Workflow Orchestrator (2 tools)

| Tool | Min. Role | Description |
|---|---|---|
| `run_create_feature_pr_workflow` | lead | 6 steps: preview → commit → push → PR → wait CI → comment on Jira |
| `get_workflow_status` | dev | Execution status (steps, result, error) |

---

## 4. Security

| Layer | Mechanism |
|---|---|
| MCP auth | `X-API-Key` header + per-CIDR IP allowlist |
| RBAC | `dev / lead / system` roles per API key; least-privilege principle |
| Rate limiting | 30 req/60s (service layer) + 10 calls/60s (MCP) per user/key |
| Sanitization | Strips tokens, RFC1918 IPs, internal hostnames, and stack traces before sending to Claude |
| Audit log | JSON-lines with UUID `request_id`; rotation at 10 MB × 5 backups |
| Safe JQL | Claude → struct → controlled builder; `_jql_escape` on all fields; MAX 50 |
| Pre-validation | Rejects empty inputs or inputs > 2000 chars before hitting the backend |
| Normalized output | LLM only receives `{key, status}` or `{key, summary}` — no internal data |
| code-agent token | `X-Agent-Token` separate from `JIRA_PAT`; value in `CODE_AGENT_TOKEN` env var |
| SSE timeout | `asyncio.wait_for` with `MCP_SSE_TIMEOUT=300s` |

---

## 5. Integrated Jira Projects

| Project | Key | Language | Type |
|---|---|---|---|
| Requirements management | `ZNRX` | es | seed (curated constraints) |
| AI and automation | `AIPROJECTS` | en | seed |
| LATAM development | `SCRX` | es | seed |
| Release / DevOps requests | `SAZ` | es | auto-discovery |
| Any other Jira project | `*` | configurable | auto-discovery on first access |

**Auto-discovery:** on first access to an unknown project, the system calls `GET /rest/api/2/project/{key}` and registers it automatically in SQLite — no manual configuration needed.

---

## 6. Test Coverage

| Suite | Tests | Coverage |
|---|---|---|
| `test-dev.sh` | 8 e2e | CLI → FastAPI → Jira |
| `test-mcp.sh` | 10 e2e | MCP tools + RBAC + pre-validation |
| `test-multi.sh` | 19 e2e | Multi-project + auto-discovery |
| `test-actions.sh` | 24 e2e | comments, assign, priority, labels, worklog, transition, clone, link, SAZ |
| `test-git.sh` | 26 e2e | Git registry CRUD + sync dry_run |
| `test-code-agent.sh` | 49 schema+live | Phases 10/11/12: tools, dispatch, RBAC |
| `pytest tests/` | 96 unit | sanitizer, jql_builder, auth, rbac, git_analyzer, git_mapper, jira_pat_routing |
| **Total** | **232** | |

Real flows validated: PRs #2574/#2575 in Azure DevOps · SAZ-7441/7442 in Jira · ZNRX-68298 via global MCP.

---

## 7. Positioning within the Zurich Global Ecosystem

### 7.1 Evaluation of et-ai-mcp-jira (skills.ai.zurich.com)

In June 2026, `et-ai-mcp-jira` (Zurich Global AI, recommended by Jose Sanchez Ros) was evaluated against the local system. Results:

| Operation | et-ai-mcp-jira | claude-mcp-jira |
|---|---|---|
| Basic CRUD (create/update/get/comment/transitions) | ✅ | ✅ |
| Search | ✅ direct JQL | ✅ NL → semantic JQL |
| **Worklog / time tracking** | ❌ | ✅ |
| link / assign / priority / labels / clone | ❌ | ✅ |
| SAZ (deployment request) | ❌ | ✅ |
| Deployment SAZ workflow | ❌ | ✅ |
| Azure DevOps EC | ❌ | ✅ |
| Git Intelligence | ❌ | ✅ |
| RBAC + corporate audit log | ❌ | ✅ |
| Jira releases / versions | ✅ | ❌ |

**Connectivity confirmed:** `gateway-dev.mcp.zurich.com` reachable from Ecuador · Jira instance = `jira.zurich.com` (Server/DC) ✅.

### 7.2 Decision and Positioning

`claude-mcp-jira` **does not compete** with `et-ai-mcp-jira` — it is a **specialized Ecuador Agent** that operates on top of the global ecosystem:

```
Claude Code
    ↓
claude-mcp-jira  [Ecuador Agent — orchestration + specialization]
    ├── Git Intelligence     → worklogs, commits, work sessions
    ├── SAZ workflow         → Ecuador deployment requests
    ├── code-agent-mcp       → Azure DevOps EC (tenant ZEC)
    └── Jira CRUD            → compatible with et-ai-mcp-jira for base CRUD
                                (future integration when gateway reaches production)
```

**Conditions for future integration with the global MCP:**
- `et-ai-mcp-jira` adds worklog and link support
- Stable production gateway (without `-dev`)
- Team-scoped tokens available (not personal)

---

## 8. Implementation Phases

| Phase | Status | Description |
|---|---|---|
| 1 — CLI Prototype | ✅ | `cli/main.py` — direct `create` command |
| 2 — Service Layer | ✅ | FastAPI + sanitization + audit log + timeouts |
| 3 — Full commands | ✅ | `update`, `summarize`, `list` + JQL + rate limiter |
| 4 — MCP Server | ✅ | SSE Docker + auth + RBAC + rate limit + normalized output |
| 4.1–4.5 — Fixes, tech debt, API improvements | ✅ | Comments, assign, priority, labels, clone, dynamic link |
| 5 — SAZ support | ✅ | `create_saz_request` + `POST /issues/saz/deployment` |
| 6 — Observability | Future | Prometheus + OpenTelemetry — enable when volume justifies it |
| 7 — Multi-project | ✅ | SQLite + lazy auto-discovery from Jira |
| 8a — Dynamic PAT | ✅ | Optional `X-Jira-Token` header; correct authorship per user |
| 8 — UI | Future | Streamlit/Next.js — after validating non-technical demand |
| 9.1–9.4 — Git Intelligence | ✅ | Scanner + analyzer + mapper + automatic worklog |
| 9.5a — Claude humanizer | ✅ | Semantic adjustment of git time estimates |
| 9.5b — Learning layer | Future | Per-user multiplier factors — requires UI |
| 10 — Workflow Orchestrator | ✅ | 6-step polling engine + 4 REST endpoints + 2 MCP tools |
| 11 — code-agent-mcp integration | ✅ | 4 MCP tools: git ops + Azure PR |
| 12 — Deployment SAZ workflow | ✅ | 3 MCP tools: deployment SAZ + PR lifecycle |
| Eval — Zurich Global MCP | ✅ | `et-ai-mcp-jira` evaluated; decision: keep local system |

---

## 9. Installation and Configuration

```bash
# Requirements: conda, Docker
conda env create -f environment.yml
conda activate claude-mcp-jira
cp .env.example .env
# Fill in: JIRA_PAT, MCP_API_KEY, CODE_AGENT_TOKEN
# Uncomment: REQUESTS_CA_BUNDLE=certs/zurichseguros-rootca-until-2031_03_20.crt

# Full stack
docker compose up

# Dev mode
bash scripts/dev.sh both    # service :18000 + MCP :18001
```

**Connect Claude Code:**
```json
{
  "mcpServers": {
    "jira": {
      "type": "sse",
      "url": "http://localhost:18001/sse",
      "headers": { "X-API-Key": "<MCP_API_KEY>" }
    }
  }
}
```

---

## 10. References

| Resource | Location |
|---|---|
| Detailed architecture | `arch/design/architecture-overview.md` |
| Implementation plan (all phases) | `arch/design/implementation-plan.md` |
| code-agent-mcp contract (23 endpoints) | `arch/code-agent/integration-plan.md` |
| Workflow Orchestrator | `arch/workflows/workflow-orchestrator.md` |
| Zurich Global MCP evaluation | `arch/evaluations/eval-zurich-mcp-integracion-2026-06-25.md` |
| Integration report vs global MCP | `arch/evaluations/eval-integracion-mcp-global-vs-local-2026-06-25.md` |
| SQLite database | `arch/bd/README.md` |
| Jira projects (constraints, TICKET_LANG) | `docs/jira-projects.md` |
| MCP Specification | https://spec.modelcontextprotocol.io |
| MCP Python SDK | https://github.com/modelcontextprotocol/python-sdk |
