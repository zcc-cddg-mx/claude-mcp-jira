# claude-mcp-jira

Integración de Claude con Jira vía MCP server interno, diseñada para entornos corporativos con red privada (Jira Server/Data Center).

## Arquitectura

```
[CLI (Typer)] → [Service Layer (FastAPI)] → [Claude API — LiteLLM proxy]
                                          → [Jira REST API v2 — jira.zurich.com]
                        ▲
               [MCP Server (Docker)]
                        ▲
               [Claude Code (CLI)]
```

El MCP server y el service layer corren dentro de la red corporativa. Ningún dato sale hacia servicios cloud externos.

## Setup

```bash
conda env create -f environment.yml
conda activate claude-mcp-jira
cp .env.example .env  # completar con JIRA_PAT y descomentar REQUESTS_CA_BUNDLE
```

## Uso

```bash
# Levantar service layer
docker compose up

# Comandos CLI
python cli/main.py create "bug login en producción prioridad alta"
python cli/main.py update PROJ-123 "cambiar prioridad a crítica"
python cli/main.py summarize PROJ-123
python cli/main.py list "mis bugs abiertos de esta semana"
```

## Estado de implementación

| Fase | Estado | Descripción |
|---|---|---|
| 1 — Prototipo CLI | ✅ Completa | Comando `create` directo |
| 2 — Service Layer | ✅ Completa | FastAPI + sanitización + audit log + timeouts |
| 3 — Comandos completos | Pendiente | `update`, `summarize`, `list` + JQL controlado |
| 4 — MCP Server | Pendiente | Servicio Docker con auth + RBAC |

## Documentación

Ver [`arch/`](arch/README.md) para arquitectura, plan de implementación e informes técnicos.
