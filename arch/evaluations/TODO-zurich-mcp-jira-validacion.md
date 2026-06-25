# TODO — Validación et-ai-mcp-jira (Zurich Global)
# Objetivo: determinar si integra con jira.zurich.com y si cubre nuestros casos de uso

---

## Ticket de prueba permanente

**ZNRX-68298** — `[MCP Claude Jira Test] Validación et-ai-mcp-jira desde Ecuador`
- Creado el 2026-06-25 vía et-ai-mcp-jira
- Usar como ticket base para todas las pruebas de esta validación (no eliminar)
- URL: https://jira.zurich.com/browse/ZNRX-68298

---

## Fase 0 — Prerequisitos ✅ COMPLETA (2026-06-25)

- [x] **Conectividad** — gateway alcanzable desde Ecuador (HTTP 200 con `-k`; firewall intercepta TLS igual que otros endpoints externos)
- [x] **Instancia Jira** — `et-ai-mcp-jira` apunta a `https://jira.zurich.com` ✅ confirmado
- [x] **Token** — válido hasta 2026-09-23; autenticado como Carlos David Duarte (82 proyectos)
- [ ] Tokens de equipo: solicitar a Jose **después** de decidir integración

**Nota técnica:** SSL requiere `-k` (o `NODE_TLS_REJECT_UNAUTHORIZED=0`) — el firewall corporativo Ecuador intercepta TLS hacia `*.mcp.zurich.com`. Mismo patrón que `api-zurich.data-fact.com`.

---

## Fase 1 — Catálogo de tools ✅ COMPLETA (2026-06-25)

21 tools disponibles en `et-ai-mcp-jira`. Modelo de auth: `jira-initialize(jira_pat)` → `session_id` → pasar en cada call.

| Tool | Función |
|---|---|
| `jira-initialize` | Crear sesión con PAT → `session_id` |
| `jira-session-status`, `check-pat-health`, `list-active-sessions` | Gestión de sesión |
| `session-diagnostics` | Diagnóstico de routing (multi-réplica) |
| `cleanup-idle-sessions-tool` | Limpieza de sesiones inactivas |
| `authenticate` | **DEPRECATED** — usar `jira-initialize` |
| `list-projects`, `get-project` | Proyectos |
| `get-issue`, `get-issue-history`, `get-comments` | Lectura |
| `search-issues` | JQL directo (max 50) |
| `create-issue`, `update-issue`, `add-comment` | Escritura básica |
| `get-transitions`, `transition-issue` | Cambio de estado |
| `get-release-issues`, `list-releases` | Releases/versiones |

**Aviso del servidor:** hay múltiples réplicas detrás del gateway — las sesiones pueden no estar disponibles entre pods. Se recomienda pasar siempre `session_id` explícito en cada llamada.

Para conectar en Claude Code (temporal, NO commitear — contiene tokens personales de Jose):
```json
{
  "mcpServers": {
    "et-ai-mcp-jira": {
      "type": "http",
      "url": "https://gateway-dev.mcp.zurich.com/servers/bc682a25af934e02a74965f1f2babb95/mcp",
      "headers": { "Authorization": "Bearer <TOKEN_MCP_JOSE>" }
    },
    "et-ai-mcp-devops-work-management": {
      "type": "http",
      "url": "https://gateway-dev.mcp.zurich.com/a2a/et-ai-mcp-devops-work-management",
      "headers": { "Authorization": "Bearer <TOKEN_AGENT_JOSE>" }
    }
  }
}
```

---

## Fase 2 — Validar operaciones contra jira.zurich.com ✅ COMPLETA (2026-06-25)

Ticket base de pruebas: **ZNRX-68298**

| Operación | Estado | Resultado |
|---|---|---|
| `search-issues` (JQL) | ✅ | Devuelve tickets ZNRX reales; JQL directo (no NL) |
| `create-issue` | ✅ | ZNRX-68298 creado; requiere `customfield_25832` (Línea de Servicio) |
| `add-comment` | ✅ | Comentario añadido a ZNRX-68171 |
| `get-issue` | ✅ | Retorna datos completos + campos custom vía `fields` param |
| `update-issue` (campos) | ✅ | Funciona; también acepta `timetracking` vía `custom_fields` |
| `get-transitions` | ✅ | ZNRX-68173: única transición disponible → ID 11 "En progreso" |
| **worklog (registrar horas)** | ❌ | **No existe tool de worklog** — ni `add-worklog`, `log-work`, `add-time`, etc. Intento vía `update-issue custom_fields worklog` devuelve 400: "Field 'worklog' cannot be set. It is not on the appropriate screen." |
| link issues | ❌ | No existe tool nativo |
| assign | ❌ | No existe tool nativo |
| set priority | ❌ | No existe tool nativo |

**Hallazgo clave — campo requerido en ZNRX:**
`customfield_25832` (Línea de Servicio) es obligatorio al crear en ZNRX. El MCP global devuelve 400 si no se pasa. Nuestro sistema lo abstrae internamente en `ZNRX_EXTRA_FIELDS`. Para integrar habría que hardcodearlo en el provider.

**Hallazgo clave — worklog no soportado:**
El MCP global no tiene tool de worklog. La única vía (`update-issue` con `worklog` en `custom_fields`) es rechazada por Jira ("not on the appropriate screen"). Registrar horas en Jira vía `et-ai-mcp-jira` **no es posible** — esta funcionalidad se mantiene exclusivamente en nuestro sistema (`sync_git_worklogs` + `/issues/{key}/worklog`).

---

## Fase 3 — Comparativa con nuestro sistema ✅ COMPLETA (2026-06-25)

| Operación | et-ai-mcp-jira | claude-mcp-jira | Veredicto |
|---|---|---|---|
| create issue | ✅ (con custom_fields) | ✅ (abstrae campos) | MCP global requiere conocimiento de campos requeridos |
| update issue | ✅ | ✅ | Equivalente |
| get issue | ✅ | ✅ | MCP global más detallado (history, comments separados) |
| search (JQL directo) | ✅ | ✅ NL→JQL | Nuestro sistema añade capa NL |
| add comment | ✅ | ✅ | Equivalente |
| get/list transitions | ✅ | ✅ | Equivalente |
| link issues | ❌ | ✅ | Gap — no tiene tool |
| assign | ❌ | ✅ | Gap — no tiene tool |
| set priority | ❌ | ✅ | Gap — no tiene tool |
| labels / clone / worklog | ❌ | ✅ | Gap |
| crear SAZ | ❌ | ✅ | Gap — específico Ecuador |
| Git Intelligence | ❌ | ✅ | Gap — mantener local |
| deployment SAZ | ❌ | ✅ | Gap — mantener local |
| Azure PR workflow | ❌ | ✅ | Gap — mantener local |
| RBAC + audit log | ❌ | ✅ | Gap — mantener local |
| NL → JQL | ❌ | ✅ | Gap — ellos usan JQL directo |
| Releases/versiones | ✅ | ❌ | MCP global tiene lo que nosotros no |

---

## Fase 4 — Decisión de integración ✅ COMPLETA (2026-06-25)

**Decisión: Opción B — Mantener sistema actual**

### Razones

| Factor | Evidencia |
|---|---|
| Worklog no soportado | El caso de uso más diferencial nuestro (Git Intelligence → worklogs) es imposible vía MCP global |
| Gaps operativos críticos | assign, priority, labels, link, clone — todos ausentes en `et-ai-mcp-jira` |
| SAZ workflow | Específico Ecuador; no existe ni existirá en el MCP global |
| Complejidad de integración | `session_id` por llamada + `customfield_25832` hardcodeado por proyecto añade fricción sin beneficio claro |
| Gateway DEV sin SLA | No se puede crear dependencia productiva sobre `gateway-dev.mcp.zurich.com` |
| Sistema actual completo | 19 MCP tools, 232 tests, end-to-end validado con PRs y SAZ reales |

### Lo que sí tomamos del MCP global

- **Posicionamiento**: nos confirmó que somos equivalentes a un "AGENTE" sobre su MCP, no un MCP plano
- **Releases/versiones**: `get-release-issues`, `list-releases` — funcionalidad que ellos tienen y nosotros no; candidata para Fase futura si hay necesidad
- **Patrón sesión PAT**: útil como referencia si en el futuro se requiere multi-usuario con PATs distintos por sesión

### Pendiente (no bloquea)

- [ ] Solicitar tokens de equipo a Jose cuando haya ambiente productivo (`gateway.mcp.zurich.com` sin `-dev`)
- [ ] Revisar `et-ai-mcp-devops-work-management` (agente A2A) — aún no evaluado; podría ser complementario para flujos genéricos globales

---

## Notas de seguridad

- ⚠️ Los tokens de Jose son PERSONALES — usar solo para validación, nunca en producción
- ⚠️ No commitear tokens en ningún archivo del repo
- ⚠️ El gateway es DEV — no crear dependencias productivas sobre él
- ⚠️ Los tickets de prueba usan prefijo `[MCP Claude Jira Test]` — ZNRX-68298 se preserva

---

## JQL de limpieza post-validación (excepto ZNRX-68298)

```
project = ZNRX AND summary ~ "[MCP Claude Jira Test]" AND key != ZNRX-68298 ORDER BY created DESC
```

---

## Fuentes

- Conversación con Jose: `logs/eval-mcp-ai-business-lead.md`
- Evaluación Copilot: `arch/evaluations/eval-mcp-zurich-copilot.md`
- Análisis estratégico: `arch/evaluations/eval-zurich-mcp-integracion-2026-06-25.md`

---

## Estado

| Fase | Estado | Notas |
|---|---|---|
| Fase 0 | ✅ Completa | Gateway alcanzable, instancia confirmada (`jira.zurich.com`), token válido |
| Fase 1 | ✅ Completa | 21 tools catalogados; modelo sesión PAT documentado |
| Fase 2 | ✅ Completa | search/create/comment/get/update/transitions ✅; worklog/link/assign/priority ❌ (no existen) |
| Fase 3 | ✅ Completa | Gaps críticos confirmados: worklog, link, assign, priority, SAZ, Git Intelligence |
| Fase 4 | ✅ Completa | **Opción B: mantener sistema actual** — worklog imposible vía MCP global; gaps críticos confirmados |
