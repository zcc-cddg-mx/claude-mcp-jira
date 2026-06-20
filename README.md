# claude-mcp-jira

Integración de Claude con Jira vía MCP server interno, diseñada para entornos corporativos con red privada (Jira Server/Data Center).

## Arquitectura

```
[CLI (Typer)]     ──HTTP──►
                            [Service Layer (FastAPI)] → [Claude API — LiteLLM proxy]
[MCP Server SSE]  ──HTTP──►                           → [Jira REST API v2 — jira.zurich.com]
```

El MCP server y el service layer corren dentro de la red corporativa. Ningún dato sale hacia servicios cloud externos.

## Setup

```bash
conda env create -f environment.yml
conda activate claude-mcp-jira
cp .env.example .env  # completar JIRA_PAT y MCP_API_KEY
```

## Uso

```bash
# Levantar stack completo (service layer + MCP server)
docker compose up

# Comandos CLI
python cli/main.py create "bug login en producción prioridad alta"
python cli/main.py update PROJ-123 "cambiar prioridad a crítica"
python cli/main.py summarize PROJ-123
python cli/main.py list "mis bugs abiertos de esta semana"
```

## Certificados corporativos

`certs/` contiene los certificados raíz Zurich. Ambos Dockerfiles los instalan automáticamente en `/etc/ssl/certs/`.

| Archivo | Uso |
|---|---|
| `zurichseguros-rootca-until-2031_03_20.crt` | Servicios internos estándar (`jira.zurich.com`) |
| `zurich-ssl-ca.pem` | SSL inspection CA (`ssldecrypt.latam.zurich.com`) — requerido para `api-zurich.data-fact.com` |
| `cacert-workflow-uat.pem` | Endpoints UAT de workflow |
| `localCA.crt` | CA de desarrollo local |

En `.env`, `REQUESTS_CA_BUNDLE` apunta al cert del endpoint que se va a llamar. Ver `.env.example` para detalles.

## Estado de implementación

| Fase | Estado | Descripción |
|---|---|---|
| 1 — Prototipo CLI | ✅ Completa | Comando `create` directo |
| 2 — Service Layer | ✅ Completa | FastAPI + sanitización + audit log + timeouts |
| 3 — Comandos completos | ✅ Completa | `update`, `summarize`, `list` + JQL controlado + rate limiter |
| 4 — MCP Server | ✅ Completa | SSE Docker + auth API key + RBAC + rate limit + output normalizado |
| 5 — Observabilidad | Opcional | Prometheus + OpenTelemetry + caching |

## Documentación

Ver [`arch/`](arch/README.md) para arquitectura, plan de implementación, evaluaciones externas e informes técnicos.
