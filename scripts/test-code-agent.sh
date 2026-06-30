#!/usr/bin/env bash
# Test e2e — Fases 10/11/12 + endpoint /deployments/saz-workflow.
# Verifica schema (tools definidos, funciones existentes, RBAC) y, con --live,
# ejecuta llamadas reales contra el service layer (:18000) y code-agent-mcp (:5001).
# Uso: bash scripts/test-code-agent.sh [--live]
#   --live: asumir que el service layer corre en :18000 y code-agent-mcp en :5001.

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=scripts/_conda_env.sh
source "$(dirname "$0")/_conda_env.sh"

# Load .env for CODE_AGENT_TOKEN if not already set
[ -f "$REPO_DIR/.env" ] && set -a && source "$REPO_DIR/.env" && set +a

SERVICE_PORT="${SERVICE_PORT:-18000}"
SERVICE_URL_LOCAL="http://localhost:$SERVICE_PORT"
MCP_PORT="${MCP_PORT:-18001}"
MCP_URL="http://localhost:$MCP_PORT"
MCP_API_KEY="${MCP_API_KEY:-super-secret-internal-key}"
CODE_AGENT_URL="${CODE_AGENT_URL:-http://localhost:5001}"
TOKEN_AZURE="${TOKEN_AZURE:-}"

PASS=0
FAIL=0
LIVE=0
[ "$1" = "--live" ] && LIVE=1

cd "$REPO_DIR"

green()  { echo -e "\033[32m✓ $*\033[0m"; }
red()    { echo -e "\033[31m✗ $*\033[0m"; }
header() { echo -e "\n\033[1m=== $* ===\033[0m"; }

assert_ok() {
    local desc="$1" output="$2" expected="$3"
    if echo "$output" | grep -qi "$expected"; then
        green "$desc"
        PASS=$((PASS+1))
    else
        red "$desc"
        echo "    Esperado: $expected"
        echo "    Obtenido: $output"
        FAIL=$((FAIL+1))
    fi
}

# ─── 1. Schema check — verificar que los 4 tools están definidos en server.py ────

header "Schema: 4 tools Fase 11 definidos en server.py"

for tool in run_code_agent get_code_agent_status create_azure_pull_request get_pull_request_status; do
    if grep -q "\"$tool\"" jira_mcp/server.py; then
        green "Tool '$tool' en server.py"
        PASS=$((PASS+1))
    else
        red "Tool '$tool' NO encontrado en server.py"
        FAIL=$((FAIL+1))
    fi
done

# ─── 2. Dispatch check — verificar que el dispatch maneja los 4 tools ────────────

header "Dispatch: 4 tools en call_tool()"

for tool in run_code_agent get_code_agent_status create_azure_pull_request get_pull_request_status; do
    if grep -q "\"$tool\"" jira_mcp/server.py && grep -A2 "\"$tool\"" jira_mcp/server.py | grep -q "service_client"; then
        green "Dispatch '$tool' → service_client"
        PASS=$((PASS+1))
    else
        red "Dispatch '$tool' no encontrado o no llama a service_client"
        FAIL=$((FAIL+1))
    fi
done

# ─── 3. service_client.py — verificar que las 4 funciones existen ────────────────

header "service_client.py: 4 funciones Fase 11"

for fn in run_code_agent get_code_agent_status create_azure_pull_request get_pull_request_status; do
    if grep -q "^def $fn" jira_mcp/service_client.py; then
        green "Función '$fn' en service_client.py"
        PASS=$((PASS+1))
    else
        red "Función '$fn' NO encontrada en service_client.py"
        FAIL=$((FAIL+1))
    fi
done

# ─── 4. code_agent_client.py — verificar que las 4 funciones existen ─────────────

header "service/clients/code_agent_client.py: 4 funciones"

for fn in run_task get_task_status prepare_and_pr get_pr_status; do
    if grep -q "^def $fn" service/clients/code_agent_client.py; then
        green "Función '$fn' en code_agent_client.py"
        PASS=$((PASS+1))
    else
        red "Función '$fn' NO encontrada en code_agent_client.py"
        FAIL=$((FAIL+1))
    fi
done

# ─── 5. Variables de entorno documentadas en .env.example ────────────────────────

header ".env.example: variables CODE_AGENT_* y TOKEN_AZURE"

for var in CODE_AGENT_URL TOKEN_AZURE CODE_AGENT_TIMEOUT; do
    if grep -q "^$var=" .env.example; then
        green "$var en .env.example"
        PASS=$((PASS+1))
    else
        red "$var NO en .env.example"
        FAIL=$((FAIL+1))
    fi
done

if ! grep -q "^CODE_AGENT_TOKEN=" .env.example && ! grep -q "^AGENT_TOKEN=" .env.example; then
    green "CODE_AGENT_TOKEN/AGENT_TOKEN eliminados de .env.example (consolidado en TOKEN_AZURE)"
    PASS=$((PASS+1))
else
    red "CODE_AGENT_TOKEN o AGENT_TOKEN aún presentes en .env.example — deben eliminarse"
    FAIL=$((FAIL+1))
fi

# ─── 6. Live tests — solo con --live y code-agent-mcp corriendo ──────────────────

if [ "$LIVE" = "1" ]; then
    header "Live: health check code-agent-mcp en $CODE_AGENT_URL"
    HEALTH=$(curl -sf "$CODE_AGENT_URL/health" 2>&1 || echo "CONNECTION_FAILED")
    assert_ok "code-agent-mcp /health" "$HEALTH" "ok"

    header "Live: POST /run en code-agent-mcp (espera 403 — repo no registrado)"
    RUN_RESP=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$CODE_AGENT_URL/run" \
        -H "Content-Type: application/json" \
        -H "X-Agent-Token: $CODE_AGENT_TOKEN" \
        -d '{
            "repo": "/nonexistent/repo",
            "branch": "feature/test",
            "files": ["/nonexistent/file.txt"],
            "ticket": "ZNRX-00000",
            "commit_message": "[TEST] code-agent e2e"
        }' 2>&1)
    if echo "$RUN_RESP" | grep -q "^4"; then
        green "POST /run → HTTP $RUN_RESP (repo no registrado, esperado 4xx)"
        PASS=$((PASS+1))
    else
        red "POST /run → HTTP $RUN_RESP (esperado 4xx)"
        FAIL=$((FAIL+1))
    fi

    header "Live: GET /repos en code-agent-mcp"
    REPOS_RESP=$(curl -s "$CODE_AGENT_URL/repos" \
        -H "X-Agent-Token: $CODE_AGENT_TOKEN" 2>&1)
    assert_ok "GET /repos → lista repos" "$REPOS_RESP" "\[\|{\"name\""

    header "Live: GET /azure/pull-requests (repo registrado)"
    PR_STATUS=$(curl -s "$CODE_AGENT_URL/azure/pull-requests/2573?repo=ov-arizona-backend-ecuador" \
        -H "X-Agent-Token: $CODE_AGENT_TOKEN" 2>&1)
    assert_ok "GET /azure/pull-requests/2573" "$PR_STATUS" "pr_id\|not found"
fi

# ─── 7. Schema check Fase 10 — 2 tools Workflow Orchestrator ─────────────────────

header "Schema: 2 tools Fase 10 definidos en server.py"

for tool in run_create_feature_pr_workflow get_workflow_status; do
    if grep -q "\"$tool\"" jira_mcp/server.py; then
        green "Tool '$tool' en server.py"
        PASS=$((PASS+1))
    else
        red "Tool '$tool' NO encontrado en server.py"
        FAIL=$((FAIL+1))
    fi
done

header "service_client.py: funciones Fase 10"

for fn in create_workflow get_workflow_status_by_id update_workflow preview_code_agent; do
    if grep -q "^def $fn" jira_mcp/service_client.py; then
        green "Función '$fn' en service_client.py"
        PASS=$((PASS+1))
    else
        red "Función '$fn' NO encontrada en service_client.py"
        FAIL=$((FAIL+1))
    fi
done

header "RBAC: permisos Fase 10"

if grep -q "run_create_feature_pr_workflow" jira_mcp/rbac.py; then
    green "run_create_feature_pr_workflow en rbac.py (lead)"
    PASS=$((PASS+1))
else
    red "run_create_feature_pr_workflow NO en rbac.py"
    FAIL=$((FAIL+1))
fi
if grep -q "get_workflow_status" jira_mcp/rbac.py; then
    green "get_workflow_status en rbac.py (dev)"
    PASS=$((PASS+1))
else
    red "get_workflow_status NO en rbac.py"
    FAIL=$((FAIL+1))
fi

header "workflow_store.py: funciones y tabla"

for fn in init_workflow_db create_execution update_execution get_execution list_executions; do
    if grep -q "^def $fn" service/clients/workflow_store.py; then
        green "Función '$fn' en workflow_store.py"
        PASS=$((PASS+1))
    else
        red "Función '$fn' NO encontrada en workflow_store.py"
        FAIL=$((FAIL+1))
    fi
done

# ─── Deployment SAZ workflow (Fase 12) ───────────────────────────────────────────

header "Schema: create_deployment_saz_workflow en server.py"

if grep -q '"create_deployment_saz_workflow"' jira_mcp/server.py; then
    green "Tool 'create_deployment_saz_workflow' definido en server.py"
    PASS=$((PASS+1))
else
    red "Tool 'create_deployment_saz_workflow' NO encontrado en server.py"
    FAIL=$((FAIL+1))
fi

if grep -q "\"developer\", \"test\", \"prod\"" jira_mcp/server.py || grep -q '"enum".*developer.*test.*prod' jira_mcp/server.py; then
    green "Enum target [developer, test, prod] en tool definition"
    PASS=$((PASS+1))
else
    red "Enum target no encontrado en tool definition"
    FAIL=$((FAIL+1))
fi

header "service_client.py: funciones deployment SAZ workflow"

for fn in get_repo_by_alias set_repo_branch_map; do
    if grep -q "^def $fn" jira_mcp/service_client.py; then
        green "Función '$fn' en service_client.py"
        PASS=$((PASS+1))
    else
        red "Función '$fn' NO encontrada en service_client.py"
        FAIL=$((FAIL+1))
    fi
done

header "saz_template.py: mapping target→base_branch"

if grep -q "_TARGET_BASE_BRANCH" service/clients/saz_template.py; then
    green "_TARGET_BASE_BRANCH dict en saz_template.py"
    PASS=$((PASS+1))
else
    red "_TARGET_BASE_BRANCH NO encontrado en saz_template.py"
    FAIL=$((FAIL+1))
fi

if grep -q "^def get_base_branch_for_target" service/clients/saz_template.py; then
    green "Función 'get_base_branch_for_target' en saz_template.py"
    PASS=$((PASS+1))
else
    red "Función 'get_base_branch_for_target' NO encontrada"
    FAIL=$((FAIL+1))
fi

header "RBAC: create_deployment_saz_workflow + set_repo_branch_map"

for tool in create_deployment_saz_workflow set_repo_branch_map; do
    if grep -q "$tool" jira_mcp/rbac.py; then
        green "$tool en rbac.py (lead+system)"
        PASS=$((PASS+1))
    else
        red "$tool NO en rbac.py"
        FAIL=$((FAIL+1))
    fi
done

header "Schema: set_repo_branch_map en server.py"

if grep -q '"set_repo_branch_map"' jira_mcp/server.py; then
    green "Tool 'set_repo_branch_map' definido en server.py"
    PASS=$((PASS+1))
else
    red "Tool 'set_repo_branch_map' NO encontrado en server.py"
    FAIL=$((FAIL+1))
fi

# ─── update_pull_request_status ──────────────────────────────────────────────────

header "Schema: update_pull_request_status en server.py"

if grep -q '"update_pull_request_status"' jira_mcp/server.py; then
    green "Tool 'update_pull_request_status' definido en server.py"
    PASS=$((PASS+1))
else
    red "Tool 'update_pull_request_status' NO encontrado en server.py"
    FAIL=$((FAIL+1))
fi

if grep -q '"abandoned".*"completed".*"active"' jira_mcp/server.py || grep -q '"enum".*abandoned' jira_mcp/server.py; then
    green "Enum status [abandoned, completed, active] en tool definition"
    PASS=$((PASS+1))
else
    red "Enum status no encontrado en tool definition"
    FAIL=$((FAIL+1))
fi

header "service_client.py: update_pull_request_status"

if grep -q "^def update_pull_request_status" jira_mcp/service_client.py; then
    green "Función 'update_pull_request_status' en service_client.py"
    PASS=$((PASS+1))
else
    red "Función 'update_pull_request_status' NO encontrada en service_client.py"
    FAIL=$((FAIL+1))
fi

header "RBAC: update_pull_request_status"

if grep -q "update_pull_request_status" jira_mcp/rbac.py; then
    green "update_pull_request_status en rbac.py (lead+system)"
    PASS=$((PASS+1))
else
    red "update_pull_request_status NO en rbac.py"
    FAIL=$((FAIL+1))
fi

# ─── Endpoint /deployments/saz-workflow (nuevo REST endpoint) ────────────────────

header "service/routes/deployment_workflow.py: router registrado"

if grep -q "deployment_workflow_router" service/main.py; then
    green "deployment_workflow_router incluido en service/main.py"
    PASS=$((PASS+1))
else
    red "deployment_workflow_router NO incluido en service/main.py"
    FAIL=$((FAIL+1))
fi

if grep -q "from .deployment_workflow import router" service/routes/__init__.py; then
    green "router importado en service/routes/__init__.py"
    PASS=$((PASS+1))
else
    red "router NO importado en service/routes/__init__.py"
    FAIL=$((FAIL+1))
fi

header "schemas: DeploymentWorkflowRequest + DeploymentWorkflowResponse"

if grep -q "class DeploymentWorkflowRequest" service/schemas/issue.py; then
    green "DeploymentWorkflowRequest definido en service/schemas/issue.py"
    PASS=$((PASS+1))
else
    red "DeploymentWorkflowRequest NO encontrado en service/schemas/issue.py"
    FAIL=$((FAIL+1))
fi

if grep -q "class DeploymentWorkflowResponse" service/schemas/issue.py; then
    green "DeploymentWorkflowResponse definido en service/schemas/issue.py"
    PASS=$((PASS+1))
else
    red "DeploymentWorkflowResponse NO encontrado en service/schemas/issue.py"
    FAIL=$((FAIL+1))
fi

for field in pr_id pr_url saz_key summary status; do
    if grep -A30 "class DeploymentWorkflowResponse" service/schemas/issue.py | grep -q "$field"; then
        green "Campo '$field' en DeploymentWorkflowResponse"
        PASS=$((PASS+1))
    else
        red "Campo '$field' NO encontrado en DeploymentWorkflowResponse"
        FAIL=$((FAIL+1))
    fi
done

header "code_agent_client.py: función prepare_and_pr usa TOKEN_AZURE"

if grep -q "TOKEN_AZURE" service/clients/code_agent_client.py; then
    green "TOKEN_AZURE usado en code_agent_client.py"
    PASS=$((PASS+1))
else
    red "TOKEN_AZURE NO encontrado en code_agent_client.py"
    FAIL=$((FAIL+1))
fi

if ! grep -q "CODE_AGENT_TOKEN\|AGENT_TOKEN" service/clients/code_agent_client.py; then
    green "CODE_AGENT_TOKEN/AGENT_TOKEN eliminados de code_agent_client.py"
    PASS=$((PASS+1))
else
    red "CODE_AGENT_TOKEN o AGENT_TOKEN aún presentes en code_agent_client.py"
    FAIL=$((FAIL+1))
fi

header "Live: /deployments/saz-workflow — validación de schema"

if [ "$LIVE" = "1" ]; then
    # Missing required fields → 422
    MISSING=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$SERVICE_URL_LOCAL/deployments/saz-workflow" \
        -H "Content-Type: application/json" \
        -d '{"repo": "ov-arizona-backend-ecuador"}' 2>&1)
    if [ "$MISSING" = "422" ]; then
        green "POST /deployments/saz-workflow sin campos requeridos → 422"
        PASS=$((PASS+1))
    else
        red "POST /deployments/saz-workflow sin campos → HTTP $MISSING (esperado 422)"
        FAIL=$((FAIL+1))
    fi

    # Empty required field → 422
    EMPTY=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$SERVICE_URL_LOCAL/deployments/saz-workflow" \
        -H "Content-Type: application/json" \
        -d '{"repo": "", "branch": "feature/test", "target": "test", "ticket": "ZNRX-00000", "task": "test task"}' 2>&1)
    if [ "$EMPTY" = "422" ]; then
        green "POST /deployments/saz-workflow con repo vacío → 422"
        PASS=$((PASS+1))
    else
        red "POST /deployments/saz-workflow con repo vacío → HTTP $EMPTY (esperado 422)"
        FAIL=$((FAIL+1))
    fi

    # code-agent-mcp not running → 502 (repo ficticio no registrado)
    NOAGENT=$(curl -s "$SERVICE_URL_LOCAL/deployments/saz-workflow" \
        -X POST -H "Content-Type: application/json" \
        -d '{"repo": "nonexistent-repo-xyz", "branch": "feature/test", "target": "test", "ticket": "ZNRX-00000", "task": "test endpoint schema"}' 2>&1)
    NOAGENT_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$SERVICE_URL_LOCAL/deployments/saz-workflow" \
        -H "Content-Type: application/json" \
        -d '{"repo": "nonexistent-repo-xyz", "branch": "feature/test", "target": "test", "ticket": "ZNRX-00000", "task": "test endpoint schema"}' 2>&1)
    if echo "$NOAGENT_CODE" | grep -q "^[45]"; then
        green "POST /deployments/saz-workflow con repo inexistente → HTTP $NOAGENT_CODE (esperado 4xx/5xx)"
        PASS=$((PASS+1))
    else
        red "POST /deployments/saz-workflow repo inexistente → HTTP $NOAGENT_CODE"
        FAIL=$((FAIL+1))
    fi

    # Response structure — only test if code-agent-mcp is up
    AGENT_HEALTH=$(curl -sf "$CODE_AGENT_URL/health" 2>/dev/null || echo "")
    if echo "$AGENT_HEALTH" | grep -qi "ok"; then
        echo "  (code-agent-mcp disponible — verificando estructura de respuesta con repo registrado)"
        REPOS=$(curl -s "$CODE_AGENT_URL/repos" -H "X-Agent-Token: $TOKEN_AZURE" 2>/dev/null)
        FIRST_REPO=$(echo "$REPOS" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r[0]['name'] if r else '')" 2>/dev/null || echo "")
        if [ -n "$FIRST_REPO" ]; then
            RESP=$(curl -s -X POST "$SERVICE_URL_LOCAL/deployments/saz-workflow" \
                -H "Content-Type: application/json" \
                -H "X-User: test-user" \
                -d "{\"repo\": \"$FIRST_REPO\", \"branch\": \"feature/[MCP Claude Jira Test]\", \"target\": \"test\", \"ticket\": \"ZNRX-00000\", \"task\": \"[MCP Claude Jira Test] endpoint schema\"}" 2>&1)
            for field in pr_id saz_key summary status; do
                if echo "$RESP" | grep -q "\"$field\""; then
                    green "Respuesta /deployments/saz-workflow contiene '$field'"
                    PASS=$((PASS+1))
                else
                    red "Respuesta /deployments/saz-workflow NO contiene '$field'"
                    echo "    Respuesta: $(echo "$RESP" | head -c 300)"
                    FAIL=$((FAIL+1))
                fi
            done
        else
            echo "  (sin repos registrados en code-agent-mcp — omitiendo test de estructura de respuesta)"
        fi
    else
        echo "  (code-agent-mcp no disponible — omitiendo test de respuesta real)"
    fi
fi

# ─── Summary ─────────────────────────────────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL=$((PASS+FAIL))
if [ "$FAIL" = "0" ]; then
    echo -e "\033[32m✓ $PASS/$TOTAL tests pasados\033[0m"
else
    echo -e "\033[31m✗ $FAIL/$TOTAL tests fallaron ($PASS pasaron)\033[0m"
fi
[ "$FAIL" = "0" ] && exit 0 || exit 1
