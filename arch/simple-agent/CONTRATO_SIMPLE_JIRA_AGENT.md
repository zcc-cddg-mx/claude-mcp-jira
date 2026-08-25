# Contrato de Desarrollo para Claude
# simple-jira-agent (SAZ Agent)

## 1. Objetivo

Desarrollar un servicio HTTP ligero denominado:

```text
simple-jira-agent
```

Su responsabilidad será la creación automatizada de tickets SAZ (Solicitud de Despliegue) en Jira para apoyar procesos de despliegue gestionados por equipos DevOps.

El agente deberá:

- Crear tickets SAZ.
- Gestionar relaciones con tickets Jira existentes.
- Asignar automáticamente el ticket.
- Mantener un historial local de solicitudes.
- Exponer una API HTTP simple y reutilizable.

---

## 2. Funcionalidades

### Crear SAZ

La solicitud deberá recibir:

- Título SAZ
- Labels
- Tipo de Solicitud
- Name
- Team Name
- Description
  - Proyecto
  - PR ID / Link
  - Rama origen
  - Rama destino

### Relación con Ticket Jira

- Opcional.
- Permitir relacionar el SAZ con otro ticket Jira.
- Utilizar relación **Required By**.

### Asignación Automática

Todos los SAZ creados deberán asignarse automáticamente a:

```text
sebastian.mayorga@zurich.com
```

---

## 3. Ejemplo de Ticket

Ticket:

```text
SAZ-7578
```

Título:

```text
Despliegue Ambiente TEST OV - BackEnd - Deducible vidrios
```

Labels:

```text
TEST
OV
```

Tipo de Solicitud:

```text
Release Management - Despliegues UAT
```

Name:

```text
Despliegue test
```

Team Name:

```text
Soporte Oficina Virtual
```

Description:

```text
Solicito su apoyo para realizar el despliegue en ambiente TEST:

Proyecto: ov-arizona-backend-ecuador
PR: 2833
Origen: feature/ZNRX-67108_textos_deducible_test_aux
Destino: test
Pull Request 2833: Nuevo deducible para vidrios
Link Azure: https://...
```

---

## 4. Arquitectura

```text
Usuario
   |
   v
simple-jira-agent
   |
   v
Jira Server/DC
```

---

## 5. Persistencia

Base de datos SQLite:

```text
jira-agent.db
```

Tabla:

```text
saz_requests
```

Campos mínimos:

```text
id
saz_key
title
project
pr_id
pr_url
source_branch
target_branch
related_issue
created_at
created_by
status
```

---

## 6. API

### Health

```http
GET /health
```

### Crear SAZ

```http
POST /saz
```

Request:

```json
{
  "title": "Despliegue Ambiente TEST OV",
  "labels": ["TEST", "OV"],
  "request_type": "Release Management - Despliegues UAT",
  "name": "Despliegue test",
  "team_name": "Soporte Oficina Virtual",
  "project": "ov-arizona-backend-ecuador",
  "pr_id": 2833,
  "pr_url": "https://dev.azure.com/...",
  "source_branch": "feature/X_test_aux",
  "target_branch": "test",
  "description": "Nuevo deducible para vidrios",
  "related_issue": "ZNRX-67108"
}
```

Response:

```json
{
  "saz_key": "SAZ-7578",
  "status": "created",
  "assignee": "sebastian.mayorga@zurich.com"
}
```

### Consultar SAZ

```http
GET /saz/{key}
```

### Historial

```http
GET /history
```

---

## 7. Relación Required By

Si se envía:

```json
{
  "related_issue": "ZNRX-67108"
}
```

El agente deberá:

1. Crear el SAZ.
2. Crear la relación Jira tipo:

```text
Required By
```

entre el SAZ y el ticket indicado.

---

## 8. Seguridad

Todos los endpoints deberán requerir:

```http
X-Agent-Token
```

Excepto:

```http
GET /health
```

---

## 9. Logging y Auditoría

Registrar:

- timestamp
- usuario
- proyecto
- PR ID
- ticket relacionado
- SAZ generado
- resultado

Formato JSON.

---

## 10. Criterios de Aceptación

1. Crear tickets SAZ correctamente.
2. Asignar automáticamente al usuario configurado.
3. Relacionar tickets mediante Required By.
4. Persistir historial en SQLite.
5. Consultar historial.
6. Devolver el identificador SAZ generado.
7. Funcionar como servicio HTTP reutilizable.

---

## 11. Evolución Prevista

### Versión 1.0

```text
Creación SAZ
Asignación automática
Historial SQLite
```

### Versión 2.0

```text
Integración con simple-pr-agent
```

### Versión 3.0

```text
Integración con Workflow Orchestrator y MCP corporativo
```
