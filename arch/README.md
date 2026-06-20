# Documentación de Arquitectura — claude-mcp-jira

## Estructura

```
arch/
├── design/                     # Diseño y plan de implementación
│   ├── architecture-overview.md    Arquitectura general (capas, componentes, flujos)
│   └── implementation-plan.md      Plan de 6 fases (+ 4.1 ajustes e2e) con decisiones y criterios de éxito
│
├── evaluations/                # Evaluaciones externas del plan
│   ├── eval-gemini.md              Evaluación y recomendaciones de Gemini
│   ├── eval-copilot.md             Evaluación de estrategia por Copilot (red corporativa)
│   ├── eval-plan-copilot.md        Review técnico del plan completo por Copilot
│   └── eval-plan-copilot-2.md      Segunda ronda: mejoras opcionales y Fase 5
│
└── reports/                    # Informes técnicos de referencia
    └── mcp-technical-report.md     Informe técnico: Model Context Protocol para evaluaciones
```

## Documentos clave

| Documento | Propósito |
|---|---|
| `design/implementation-plan.md` | Fuente de verdad del plan — decisiones, fases, criterios |
| `reports/mcp-technical-report.md` | Referencia técnica MCP para auditorías y evaluaciones futuras |
| `evaluations/eval-plan-copilot-2.md` | Última evaluación — mejoras opcionales adoptadas y elementos diferidos a Fase 5 |
| `../docs/jira-projects.md` | Metadata real de proyectos: ZNRX, AIPROJECTS, SAZ, SCRX |
| `../docs/jira-fields.md` | Campos requeridos/opcionales y valores permitidos por proyecto |
| `../docs/jira-roles.md` | Permisos efectivos del usuario en los 4 proyectos |
| `../docs/jira-link-types.md` | 29 link types — recomendación para SAZ→ZNRX (Fase 5) |
| `../docs/jira-workflows.md` | Statuses y transiciones por proyecto |
