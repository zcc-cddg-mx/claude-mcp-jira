# Recomendaciones de Evolución
# claude-mcp-jira como Servicio Permanente

## Objetivo

Evolucionar `claude-mcp-jira` desde una herramienta utilizada principalmente desde Claude Code hacia una plataforma de servicios internos siempre disponible, desacoplada del cliente y reutilizable por scripts, interfaces web y otros agentes.

---

# Visión Objetivo

```text
Script/UI/Claude
      |
      v
localhost:18000
(claude-mcp-jira)
      |
      +------------------+
      |                  |
      v                  v
simple-jira-agent   simple-pr-agent
      |                  |
      v                  v
    Jira            Azure DevOps
```

---

# Recomendación Principal

Convertir `claude-mcp-jira` en el punto único de entrada para todas las capacidades de automatización.

El puerto:

```text
localhost:18000
```

no debe exponer únicamente workflows, sino TODAS las capacidades funcionales de la plataforma.

Esto transforma a `claude-mcp-jira` en un verdadero:

```text
Developer Automation API Gateway
```

---

# Exposición Completa de Capacidades

## Nivel 1 - Jira Core

```text
POST   /jira/issues
PATCH  /jira/issues/{key}
POST   /jira/issues/{key}/comments
POST   /jira/issues/{key}/link
POST   /jira/issues/{key}/worklog
POST   /jira/issues/{key}/transition
```

## Nivel 2 - Git Intelligence

```text
POST /git/repos/register
GET  /git/repos
POST /git/worklog/sync
POST /git/worklog/estimate
```

## Nivel 3 - Pull Requests

```text
POST /prs/create
GET  /prs/{id}
```

Delegados internamente a:

```text
simple-pr-agent
```

## Nivel 4 - SAZ

```text
POST /saz/create
GET  /saz/history
```

Delegados internamente a:

```text
simple-jira-agent
```

## Nivel 5 - Workflows

```text
POST /workflows/create-feature-pr
POST /workflows/deployment
POST /workflows/worklog-sync
GET  /workflows/{id}
```

Estos workflows representan la principal propuesta de valor del sistema.

---

# Servicio Permanente

Ejecutar como servicio del sistema:

```bash
systemctl enable claude-mcp-jira
systemctl start claude-mcp-jira
```

Beneficios:

- Siempre disponible.
- Independiente de Claude Code.
- Reutilizable por múltiples clientes.
- Menor tiempo de respuesta.

---

# Script Interactivo Oficial

Crear:

```text
developer-assistant.sh
```

o

```text
developer-assistant.py
```

Funciones:

- Crear PR.
- Crear SAZ.
- Registrar horas.
- Ejecutar workflows.
- Consultar estado.

El script únicamente consumirá la API localhost:18000.

---

# Configuración por Usuario

Archivo:

```text
~/.developer-assistant/config.json
```

Ejemplo:

```json
{
  "default_project": "ZNRX",
  "default_repo": "ov-arizona-backend-ecuador"
}
```

---

# Agentes Especializados

## simple-pr-agent

Responsable de:

- Pull Requests.
- Estado PR.
- Azure DevOps.

## simple-jira-agent

Responsable de:

- SAZ.
- Relaciones Jira.
- Historial.

## claude-mcp-jira

Responsable de:

- Orquestación.
- IA.
- Git Intelligence.
- Workflows.
- API Gateway.

---

# Roadmap Recomendado

## Fase 1

- Servicio permanente.
- systemd.
- API Gateway en 18000.
- Script interactivo.

## Fase 2

- Integración simple-pr-agent.
- Integración simple-jira-agent.

## Fase 3

- Workflows corporativos.
- Configuración por usuario.

## Fase 4

- UI Web.
- Dashboard.

## Fase 5

- Skill corporativa alineada con Zurich.

---

# Conclusión

La evolución recomendada no consiste en añadir más herramientas MCP.

La evolución consiste en consolidar `claude-mcp-jira` como plataforma central de automatización, exponiendo todas sus capacidades mediante una única API en localhost:18000 y utilizando agentes especializados para las operaciones concretas.

De esta forma, Claude, scripts, UI y futuras skills corporativas consumirán exactamente el mismo contrato funcional.
