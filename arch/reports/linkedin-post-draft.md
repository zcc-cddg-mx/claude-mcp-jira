# Borrador — Post LinkedIn

**Audiencia objetivo:** profesionales de tecnología, equipos de desarrollo, líderes técnicos en seguros / LATAM  
**Tono:** profesional pero personal; muestra impacto real, no solo tecnología  
**Idioma:** español

---

## Versión A — orientada a impacto operativo (recomendada)

---

Durante los últimos meses construí un agente de IA que cambió la forma en que trabajo como desarrollador en Zurich Insurance Ecuador.

**El problema era simple:** pasaba demasiado tiempo en tareas que no eran desarrollo. Crear tickets Jira, solicitar despliegues al equipo DevOps, registrar horas trabajadas, coordinar Pull Requests en Azure DevOps. Todo manual. Todo interrumpiendo el flujo.

**La solución:** `claude-mcp-jira` — una plataforma de automatización construida sobre el protocolo MCP de Anthropic, integrada 100% en la red interna de Zurich.

Lo que hace hoy:

🔹 **Git Intelligence** — analiza el historial de commits, detecta sesiones de trabajo, infiere el ticket Jira desde el nombre de la rama y registra las horas automáticamente. Lo que antes tomaba 15 minutos al final del día, ahora es un comando.

🔹 **Deployment SAZ workflow** — un solo comando crea el PR en Azure DevOps y genera el ticket de solicitud de despliegue (SAZ) en Jira, vinculado al requerimiento. Tiempo real: de ~20 minutos a menos de 1 minuto.

🔹 **20 herramientas MCP** disponibles desde el IDE (Claude Code) o desde el CLI — crear tickets, buscar, comentar, asignar, transicionar, clonar, linkear, todo en lenguaje natural.

🔹 **Siempre disponible** — corre como servicio systemd, arranca con el sistema, se reinicia solo si cae.

240 tests. Red 100% interna. Evaluado y comparado contra el MCP global de Zurich — con capacidades que el ecosistema global aún no tiene.

El mayor aprendizaje: la IA no reemplaza al desarrollador. Elimina la fricción entre el desarrollador y las herramientas que rodean al desarrollo.

¿Alguien más en el sector seguros está explorando automatización de DevOps con agentes de IA? Me interesa conectar.

---

#InteligenciaArtificial #DevOps #Automatización #Jira #AzureDevOps #MCP #Anthropic #ZurichInsurance #DesarrolloDeSoftware #LATAM

---

## Versión B — orientada a tecnología / audiencia técnica

---

Llevo meses construyendo un agente de IA para automatizar el ciclo de desarrollo en Zurich Insurance Ecuador. Hoy está en producción y quiero compartir qué aprendí.

**La arquitectura:**

```
Claude Code (IDE)  ──SSE/MCP──►  MCP Server  ──HTTP──►  Service Layer
CLI developer-assistant  ──────────────────────────────►  :18000

Service Layer  ──►  Jira REST API v2 (Server/DC)
               ──►  Claude API (vía LiteLLM proxy interno)
               ──►  code-agent-mcp  ──►  Azure DevOps EC
```

Construido sobre el **Model Context Protocol (MCP)** de Anthropic — el estándar abierto que permite conectar LLMs con servicios externos de forma segura y auditable.

**Lo más interesante que construí:**

→ **Git Intelligence**: escanea `git log`, detecta sesiones por gaps temporales, extrae el ticket Jira desde el nombre de la rama con regex, estima el tiempo por tipo de cambio, y Claude ajusta semánticamente la estimación (debugging × 1.5, trabajo nocturno + 15min). Todo en `dry_run=True` por defecto — el desarrollador confirma antes de registrar.

→ **Deployment SAZ workflow**: un endpoint sincrónico que orquesta dos agentes especializados (`simple-pr-agent` en Azure DevOps y `simple-jira-agent` para SAZ), expuesto también como herramienta MCP y como comando CLI.

→ **Siempre disponible sin Claude Code**: `systemctl --user start claude-mcp-jira` arranca el stack completo. `da deploy` es suficiente.

**Restricciones que lo hicieron más interesante:**
- Jira Server/Data Center (no Cloud) → API v2, PAT Bearer, sin accountId
- Certificados corporativos propios
- Red 100% interna — zero tráfico externo

20 herramientas MCP · 240 tests · funcionando con PRs y SAZs reales.

El código vive dentro de la red Zurich, pero el patrón es replicable. Happy to discuss.

---

#MCP #ModelContextProtocol #Anthropic #ClaudeAI #DevOps #Automatización #Jira #AzureDevOps #PythonDev #SoftwareEngineering

---

## Notas de edición

- **Versión A** es más adecuada para publicación general — mayor alcance, más compartible
- **Versión B** atrae a perfiles técnicos — menor alcance pero más calidad de conexiones
- Ambas evitan mencionar datos internos sensibles (URLs, tokens, nombres de proyectos específicos de negocio)
- El diagrama ASCII en Versión B puede eliminarse si LinkedIn no lo renderiza bien
- Ajustar el cierre ("¿Alguien más...") según el objetivo: networking, visibilidad, o búsqueda de oportunidades
