#!/usr/bin/env bash
# Test e2e — Fase 11: integración con code-agent-mcp.
# Verifica que los 4 MCP tools existen en el server y que el cliente HTTP
# intenta conectarse al code-agent-mcp (espera falla de conexión si no está corriendo).
# Uso: bash scripts/test-code-agent.sh [--live]
#   --live: asumir que code-agent-mcp corre en CODE_AGENT_URL y ejecutar llamadas reales.

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=scripts/_conda_env.sh
source "$(dirname "$0")/_conda_env.sh"

MCP_PORT="${MCP_PORT:-18001}"
MCP_URL="http://localhost:$MCP_PORT"
MCP_API_KEY="${MCP_API_KEY:-test-key}"
CODE_AGENT_URL="${CODE_AGENT_URL:-http://localhost:5001}"

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

header ".env.example: variables CODE_AGENT_*"

for var in CODE_AGENT_URL CODE_AGENT_TOKEN CODE_AGENT_TIMEOUT; do
    if grep -q "^$var=" .env.example; then
        green "$var en .env.example"
        PASS=$((PASS+1))
    else
        red "$var NO en .env.example"
        FAIL=$((FAIL+1))
    fi
done

# ─── 6. Live tests — solo con --live y code-agent-mcp corriendo ──────────────────

if [ "$LIVE" = "1" ]; then
    header "Live: health check code-agent-mcp en $CODE_AGENT_URL"
    HEALTH=$(curl -sf "$CODE_AGENT_URL/health" 2>&1 || echo "CONNECTION_FAILED")
    assert_ok "code-agent-mcp /health" "$HEALTH" "ok"

    header "Live: MCP tool run_code_agent (espera error 4xx/5xx sin repo real)"
    MCP_RESP=$(curl -s -X POST "$MCP_URL/messages" \
        -H "Content-Type: application/json" \
        -H "x-api-key: $MCP_API_KEY" \
        -d '{
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "run_code_agent",
                "arguments": {
                    "repo": "/nonexistent/path",
                    "branch": "feature/test",
                    "files": ["/nonexistent/file.txt"],
                    "ticket": "ZNRX-00000",
                    "commit_message": "[TEST] code-agent Fase 11 e2e"
                }
            },
            "id": 1
        }' 2>&1)
    assert_ok "run_code_agent via MCP (respuesta recibida)" "$MCP_RESP" "task_id\|Error\|error"
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
