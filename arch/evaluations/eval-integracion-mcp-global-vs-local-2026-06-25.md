# Informe técnico — Evaluación et-ai-mcp-jira vs MCP local (claude-mcp-jira)
# Fecha: 2026-06-25
# Contexto: Recomendación de Jose Luis Sanchez Ros (AI Business Solutions Lead, Zurich España)
# Resultado: Validación completa realizada el mismo día de la recomendación

---

## Resumen ejecutivo

Se realizó una evaluación técnica completa de `et-ai-mcp-jira` (Zurich global) contra el sistema `claude-mcp-jira` (Zurich Ecuador). La validación confirmó que el MCP global es funcional y alcanzable desde Ecuador, pero **no cubre los casos de uso críticos del equipo** — en particular el registro de horas (worklog), los flujos SAZ de despliegue y la integración con Azure DevOps Ecuador.

**Decisión: mantener `claude-mcp-jira` como sistema principal.** El MCP global es una referencia de posicionamiento válida, no una capa de sustitución.

---

## 1. Contexto de la evaluación

Jose Sanchez Ros recomendó explorar las skills globales de Zurich antes de continuar desarrollando desde cero:

> "Antes de la UI, mira los MCPs de Jira que tenemos"  
> "please antes de hacer un mcp de 0 piensa que tenemos muchos"  
> "haz una skill que funcione muy bien y se comporte como quieres"

Skills evaluadas:
- `et-ai-mcp-jira` — MCP de Jira sobre `gateway-dev.mcp.zurich.com`
- `et-ai-mcp-devops-work-management` — Agente A2A DevOps (pendiente de evaluar)

---

## 2. Resultados de conectividad

| Prueba | Resultado |
|---|---|
| Conectividad desde Ecuador | ✅ HTTP 200; latencia ~700ms |
| SSL / TLS | Requiere `-k` — firewall Ecuador intercepta TLS (mismo patrón que otros endpoints externos) |
| Instancia Jira | ✅ `https://jira.zurich.com` — nuestra instancia Server/DC |
| Autenticación | ✅ PAT de equipo Ecuador funciona vía `jira-initialize` |
| Token de Jose | Válido hasta 2026-09-23; personal — no usar en producción |

---

## 3. Catálogo de tools disponibles (21)

| Categoría | Tools |
|---|---|
| Sesión | `jira-initialize`, `jira-session-status`, `check-pat-health`, `list-active-sessions`, `session-diagnostics`, `cleanup-idle-sessions-tool`, `authenticate` (deprecated) |
| Proyectos | `list-projects`, `get-project` |
| Lectura | `get-issue`, `get-issue-history`, `get-comments` |
| Búsqueda | `search-issues` (JQL directo, max 50) |
| Escritura | `create-issue`, `update-issue`, `add-comment` |
| Estado | `get-transitions`, `transition-issue` |
| Releases | `get-release-issues`, `list-releases` |

**Modelo de autenticación:** `jira-initialize(jira_pat)` → `session_id` → pasar en cada llamada. El gateway tiene múltiples réplicas — el `session_id` debe pasarse explícitamente siempre.

---

## 4. Operaciones validadas contra jira.zurich.com

| Operación | Resultado | Detalle |
|---|---|---|
| `search-issues` | ✅ | JQL directo; devuelve tickets ZNRX reales |
| `create-issue` | ✅ | Creado ZNRX-68298; requiere `customfield_25832` (Línea de Servicio) |
| `add-comment` | ✅ | Comentario añadido a ZNRX-68171 |
| `get-issue` | ✅ | Datos completos + campos custom vía `fields` |
| `update-issue` | ✅ | Funciona incluido `timetracking` vía `custom_fields` |
| `get-transitions` | ✅ | Transiciones reales de la instancia |
| **worklog (registrar horas)** | ❌ | **No existe tool.** Intento vía `update-issue.worklog` → 400 Jira: "not on the appropriate screen" |
| link issues | ❌ | No existe tool |
| assign | ❌ | No existe tool |
| set priority | ❌ | No existe tool |
| labels / clone | ❌ | No existe tool |

---

## 5. Comparativa funcional

| Operación | et-ai-mcp-jira | claude-mcp-jira | Decisión |
|---|---|---|---|
| create / update / get | ✅ | ✅ | Equivalente; MCP global expone campos requeridos al llamador |
| search | ✅ JQL directo | ✅ NL→JQL controlado | Nuestro sistema añade capa semántica |
| comment / transitions | ✅ | ✅ | Equivalente |
| **worklog** | ❌ | ✅ | **Mantener local** — caso de uso principal de Git Intelligence |
| link / assign / priority / labels / clone | ❌ | ✅ | **Mantener local** |
| SAZ (solicitud de despliegue) | ❌ | ✅ | **Mantener local** — específico Zurich Ecuador |
| Deployment SAZ workflow | ❌ | ✅ | **Mantener local** |
| Azure DevOps PR | ❌ | ✅ | **Mantener local** — tenant ZEC |
| Git Intelligence (worklogs desde commits) | ❌ | ✅ | **Mantener local** |
| NL → JQL semántico | ❌ | ✅ | **Mantener local** |
| RBAC + audit log | ❌ | ✅ | **Mantener local** |
| **Releases / versiones** | ✅ | ❌ | MCP global tiene algo que nosotros no — candidato futuro |

---

## 6. Hallazgos técnicos relevantes

**Campo requerido en ZNRX:**  
`customfield_25832` (Línea de Servicio) es obligatorio al crear tickets en ZNRX. El MCP global expone este detalle al llamador (devuelve 400 si no se pasa). `claude-mcp-jira` lo abstrae internamente en `ZNRX_EXTRA_FIELDS` — ventaja para el usuario final.

**Worklog bloqueado a nivel Jira:**  
El campo `worklog` no está disponible en la pantalla de edición de ZNRX vía API sin contexto de transición. Incluso teniendo acceso directo a la API REST de Jira, el endpoint `/rest/api/2/issue/{key}/worklog` sí funciona — lo que falla es la vía de `update-issue`. Nuestro sistema usa el endpoint dedicado, por eso funciona.

**Agente A2A no evaluado:**  
`et-ai-mcp-devops-work-management` está pendiente. Podría ser complementario para flujos genéricos globales, pero no reemplaza la integración con Azure DevOps Ecuador (tenant `ZurichInsurance-EC / Oficina-Virtual-ZEC`).

---

## 7. Decisión

**Opción B: mantener `claude-mcp-jira` como sistema principal.**

| Criterio | Peso |
|---|---|
| Worklog imposible vía MCP global | Crítico — es el caso de uso diferencial del equipo |
| 6+ gaps en operaciones cotidianas | Alto — assign, priority, link, labels son uso diario |
| SAZ y Azure DevOps específicos Ecuador | Crítico — no existirán en el MCP global |
| Gateway DEV sin SLA | Medio — no se puede crear dependencia productiva |
| Complejidad de integración (`session_id` + campos requeridos por proyecto) | Medio — fricción sin beneficio neto |

---

## 8. Recomendación al equipo global (para Jose)

El MCP global cubre el 40% de las operaciones — CRUD básico y lectura. El 60% restante (worklogs, SAZ, Azure DevOps Ecuador, Git Intelligence, RBAC) es específico del flujo de desarrollo de Zurich Ecuador y no tiene equivalente en las skills globales actuales.

**Posicionamiento propuesto:**  
`claude-mcp-jira` se comporta como un **AGENTE especializado Ecuador** encima del ecosistema Zurich — no compite con `et-ai-mcp-jira`, lo complementa con lógica de negocio local.

**Para colaboración futura con el equipo global:**
- Cuando `gateway-dev` tenga un ambiente productivo estable → reevaluar como capa base para CRUD
- Si `et-ai-mcp-jira` añade worklog y link → reconsiderar delegación del CRUD básico
- Evaluar `et-ai-mcp-devops-work-management` para ver si cubre Azure DevOps EC (tenant ZEC)

---

## 9. Ticket de prueba

**ZNRX-68298** — `[MCP Claude Jira Test] Validación et-ai-mcp-jira desde Ecuador`  
Creado durante la validación. Se preserva como referencia. No eliminar.

---

## Referencias

| Documento | Ruta |
|---|---|
| TODO validación detallado | `arch/evaluations/TODO-zurich-mcp-jira-validacion.md` |
| Estado del sistema actual | `arch/evaluations/eval-estado-actual-2026-06-25.md` |
| Evaluación Copilot | `arch/evaluations/eval-mcp-zurich-copilot.md` |
| Análisis estratégico | `arch/evaluations/eval-zurich-mcp-integracion-2026-06-25.md` |
| Conversación con Jose | `logs/eval-mcp-ai-business-lead.md` |
