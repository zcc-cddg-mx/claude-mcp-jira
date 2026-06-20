# Tipos de link Jira — jira.zurich.com

Obtenido de `GET /rest/api/2/issueLinkType`. Relevante para la Fase 5 (vincular SAZ → ZNRX).

## Recomendación para SAZ → ZNRX

Para vincular un ticket SAZ a su ZNRX de origen, usar **"Relates"** (id `10003`):

```json
POST /rest/api/2/issueLink
{
  "type": { "id": "10003" },
  "inwardIssue":  { "key": "ZNRX-XXXXX" },
  "outwardIssue": { "key": "SAZ-YYYYY" }
}
```

Semántica: `SAZ-YYYYY` *relates to* `ZNRX-XXXXX`.

Alternativa si se quiere expresar dependencia explícita: **"Blocks"** (id `10000`) —
`ZNRX-XXXXX` *is blocked by* `SAZ-YYYYY` (el ZNRX no avanza hasta resolver el SAZ).

---

## Lista completa

| id | Nombre | Outward (origen → destino) | Inward (destino ← origen) |
|---|---|---|---|
| 10000 | Blocks | blocks | is blocked by |
| 10001 | Cloners | clones | is cloned by |
| 10002 | Duplicate | duplicates | is duplicated by |
| 10003 | **Relates** | relates to | relates to |
| 10300 | Problem/Incident | causes | is caused by |
| 10400 | Inclusion | includes | is included by |
| 10401 | Dependency | depends on | has a dependency to |
| 10500 | Requirement | Require | required by |
| 10603 | Tests | tests | tested by |
| 10700 | Defect | created | created by |
| 10800 | Issue split | split to | split from |
| 10900 | Implements | implements | is implemented by |
| 10901 | Bonfire Testing | Discovered while testing | Testing discovered |
| 11000 | Analyses | Analyses | Is analysed by |
| 11100 | Agile Hive Dependency Link | requires | is required by |
| 11101 | Agile Hive Link | Child of | Parent of |
| 11102 | Agile Hive Objective Link | Belongs to Objective | Is Objective of |
| 11103 | Agile Hive Risk Link | Treats | Is treated by |
| 11104 | Gantt End to End | has to be finished together with | has to be finished together with |
| 11105 | Gantt End to Start | has to be done before | has to be done after |
| 11106 | Gantt Start to End | earliest end is start of | start is earliest end of |
| 11107 | Gantt Start to Start | has to be started together with | has to be started together with |
| 11500 | Released By | Is Released by | Releases |
| 11600 | Owns | Is owned by | Owns |
| 11800 | Replace | replaces | is replaced by |
| 11900 | Changes | changes | is changed by |
| 11901 | Affects | affects | is affected by |
| 11902 | Agile Hive Strategic Theme Link | belongs to Theme | is Theme of |

---

## Uso por caso de negocio

| Caso | Link type recomendado | Dirección |
|---|---|---|
| SAZ → ZNRX (solicitud DevOps vinculada a requerimiento) | **Relates** (10003) | SAZ *relates to* ZNRX |
| ZNRX bloqueado hasta resolver SAZ | **Blocks** (10000) | ZNRX *is blocked by* SAZ |
| Ticket duplicado | **Duplicate** (10002) | nuevo *duplicates* original |
| Bug causado por un issue | **Problem/Incident** (10300) | bug *is caused by* issue |
| Epic que incluye stories | **Inclusion** (10400) | epic *includes* story |
| Test que verifica una story | **Tests** (10603) | test *tests* story |
