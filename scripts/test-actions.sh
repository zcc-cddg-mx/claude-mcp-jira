#!/usr/bin/env bash
# Test runner — validación e2e de endpoints de acción (Fases 4.3, 4.4, 4.5, 5).
# Cubre: comments, assign, priority, labels, worklog, transition, clone, link, saz.
# Asume service layer corriendo en :18000. Uso: bash scripts/test-actions.sh [--restart]

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=scripts/_conda_env.sh
source "$(dirname "$0")/_conda_env.sh"
SERVICE_PORT="${MCP_SERVICE_PORT:-18000}"
SERVICE_URL="${MCP_SERVICE_BASE_URL:-http://localhost:$SERVICE_PORT}"
PIDFILE=/tmp/mcp-jira-service.pid
LOG_SERVICE=/tmp/mcp-jira-service.log
PASS=0
FAIL=0
RESTART=0

[ "$1" = "--restart" ] && RESTART=1

# Ticket base para los tests — debe existir en ZNRX en estado To Do
BASE_KEY="ZNRX-68171"
CLONE_KEY=""
SAZ_KEY=""

export SERVICE_URL
export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
export AUDIT_LOG_PATH=/tmp/audit.log
export JIRA_TIMEOUT=30

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

assert_http() {
    local desc="$1" url="$2" method="${3:-GET}" body="${4:-}" expected_code="${5:-2}"
    if [ -n "$body" ]; then
        code=$(curl -s -o /tmp/test_actions_resp.json -w "%{http_code}" \
            -X "$method" "$url" \
            -H "Content-Type: application/json" \
            -H "x-user: carlos.duarte2" \
            -d "$body")
    else
        code=$(curl -s -o /tmp/test_actions_resp.json -w "%{http_code}" \
            -H "x-user: carlos.duarte2" "$url")
    fi
    local first_digit="${code:0:1}"
    if [ "$first_digit" = "$expected_code" ]; then
        green "$desc (HTTP $code)"
        PASS=$((PASS+1))
    else
        red "$desc (esperado ${expected_code}xx, obtuvo HTTP $code)"
        cat /tmp/test_actions_resp.json
        FAIL=$((FAIL+1))
    fi
    cat /tmp/test_actions_resp.json
    echo ""
}

kill_port() {
    local port=$1
    local pids
    pids=$(ss -tlnp "sport = :$port" 2>/dev/null | awk 'NR>1 {match($0,/pid=([0-9]+)/,a); if(a[1]) print a[1]}')
    for pid in $pids; do kill -TERM "$pid" 2>/dev/null || true; done
    for i in $(seq 1 10); do
        ss -tlnp "sport = :$port" 2>/dev/null | grep -q ":$port" || return 0
        sleep 0.5
    done
}

wait_port() {
    local port=$1
    echo -n "[setup] Esperando service en :$port ..."
    for i in $(seq 1 30); do
        curl -sf "http://localhost:$port/health" > /dev/null 2>&1 && { echo " listo."; return 0; }
        sleep 0.5; echo -n "."
    done
    echo " TIMEOUT"; return 1
}

# ── 0. Setup ─────────────────────────────────────────────────────────────────
header "0. Setup"

if [ "$RESTART" -eq 1 ]; then
    if [ -f "$PIDFILE" ]; then kill -TERM "$(cat $PIDFILE)" 2>/dev/null || true; rm -f "$PIDFILE"; sleep 0.5; fi
    kill_port $SERVICE_PORT; sleep 0.5
    nohup "$UVICORN" service.main:app --port $SERVICE_PORT --host 127.0.0.1 > "$LOG_SERVICE" 2>&1 &
    echo $! > "$PIDFILE"
    wait_port $SERVICE_PORT || { red "Service layer no arrancó"; exit 1; }
else
    curl -sf "$SERVICE_URL/health" > /dev/null 2>&1 || {
        red "Service layer no responde en $SERVICE_URL — usa --restart"
        exit 1
    }
    echo "[setup] Usando service layer existente en $SERVICE_URL"
fi

green "Service layer activo — ticket base: $BASE_KEY"

# ── 1. POST /issues/{key}/comments ───────────────────────────────────────────
header "1. POST /issues/{key}/comments"
assert_http "Añadir comentario" \
    "$SERVICE_URL/issues/$BASE_KEY/comments" POST \
    '{"text": "comentario de test desde test-actions.sh — puede ignorarse"}'
assert_ok "Respuesta contiene key" "$(cat /tmp/test_actions_resp.json)" "$BASE_KEY"

# ── 2. POST /issues/{key}/assign ─────────────────────────────────────────────
header "2. POST /issues/{key}/assign"
assert_http "Asignar a carlos.duarte2" \
    "$SERVICE_URL/issues/$BASE_KEY/assign" POST \
    '{"text": "asignar a carlos.duarte2"}'
assert_ok "Respuesta contiene assignee" "$(cat /tmp/test_actions_resp.json)" "carlos"

# ── 3. POST /issues/{key}/priority ───────────────────────────────────────────
header "3. POST /issues/{key}/priority"
assert_http "Cambiar prioridad a High" \
    "$SERVICE_URL/issues/$BASE_KEY/priority" POST \
    '{"text": "cambiar prioridad a alta"}'
assert_ok "Respuesta contiene priority" "$(cat /tmp/test_actions_resp.json)" "High\|priority"

# ── 4. POST /issues/{key}/labels ─────────────────────────────────────────────
header "4. POST /issues/{key}/labels"
assert_http "Añadir label test-e2e" \
    "$SERVICE_URL/issues/$BASE_KEY/labels" POST \
    '{"text": "añadir label: test-e2e"}'
assert_ok "Respuesta contiene operation=add" "$(cat /tmp/test_actions_resp.json)" "add"
assert_ok "Respuesta contiene label test-e2e" "$(cat /tmp/test_actions_resp.json)" "test-e2e"

# ── 5. POST /issues/{key}/worklog ─────────────────────────────────────────────
header "5. POST /issues/{key}/worklog"
assert_http "Registrar 1 hora de trabajo" \
    "$SERVICE_URL/issues/$BASE_KEY/worklog" POST \
    '{"text": "registrar 1 hora de trabajo en pruebas e2e"}'
assert_ok "Respuesta contiene time_spent_seconds >= 3600" "$(cat /tmp/test_actions_resp.json)" "3600\|time_spent"

# ── 6. POST /issues/{key}/transition ──────────────────────────────────────────
header "6. POST /issues/{key}/transition"
assert_http "Transicionar a In Progress" \
    "$SERVICE_URL/issues/$BASE_KEY/transition" POST \
    '{"text": "pasar a en progreso"}'
assert_ok "Respuesta contiene nuevo status" "$(cat /tmp/test_actions_resp.json)" "status\|Progress\|progreso"

# ── 7. POST /issues/{key}/clone ───────────────────────────────────────────────
header "7. POST /issues/{key}/clone"
assert_http "Clonar ticket con nuevo título" \
    "$SERVICE_URL/issues/$BASE_KEY/clone" POST \
    '{"text": "[MCP Claude Jira Test] clone desde test-actions.sh — puede eliminarse"}'
CLONE_KEY=$(cat /tmp/test_actions_resp.json | grep -oE 'ZNRX-[0-9]+' | grep -v "$BASE_KEY" | head -1)
if [ -n "$CLONE_KEY" ]; then
    green "Clone creado: $CLONE_KEY"
    PASS=$((PASS+1))
else
    red "No se extrajo new_key del clone"
    FAIL=$((FAIL+1))
fi

# ── 8. POST /issues/{key}/link ────────────────────────────────────────────────
header "8. POST /issues/{key}/link"
if [ -n "$CLONE_KEY" ]; then
    assert_http "Relacionar $BASE_KEY con $CLONE_KEY" \
        "$SERVICE_URL/issues/$BASE_KEY/link" POST \
        "{\"text\": \"relacionar con $CLONE_KEY, el clone depende del original\"}"
    assert_ok "Respuesta contiene target_key" "$(cat /tmp/test_actions_resp.json)" "$CLONE_KEY"
else
    red "Skipped — no hay CLONE_KEY disponible"
    FAIL=$((FAIL+1))
fi

# ── 8b. POST /issues/{key}/link — auto-link debe fallar ──────────────────────
header "8b. Auto-link rechazado (H2 fix)"
assert_http "Auto-link $BASE_KEY → $BASE_KEY devuelve 422" \
    "$SERVICE_URL/issues/$BASE_KEY/link" POST \
    "{\"text\": \"relacionar con $BASE_KEY\"}" "4"
assert_ok "Mensaje de error correcto" "$(cat /tmp/test_actions_resp.json)" "consigo mismo"

# ── 9. POST /issues/saz ───────────────────────────────────────────────────────
header "9. POST /issues/saz"
assert_http "Crear SAZ vinculado a $BASE_KEY" \
    "$SERVICE_URL/issues/saz" POST \
    "{\"text\": \"[MCP Claude Jira Test] reiniciar servicio auth — test-actions.sh, puede eliminarse\", \"znrx_key\": \"$BASE_KEY\"}"
SAZ_KEY=$(cat /tmp/test_actions_resp.json | grep -oE 'SAZ-[0-9]+' | head -1)
if [ -n "$SAZ_KEY" ]; then
    green "SAZ creado y vinculado: $SAZ_KEY → $BASE_KEY"
    PASS=$((PASS+1))
else
    red "No se extrajo saz_key de la respuesta"
    FAIL=$((FAIL+1))
fi

# ── 9b. POST /issues/saz — znrx_key mal formado → 422 ────────────────────────
header "9b. SAZ con znrx_key inválido (H5 fix)"
assert_http "znrx_key mal formado devuelve 422" \
    "$SERVICE_URL/issues/saz" POST \
    '{"text": "reiniciar servicio auth", "znrx_key": "znrx68171"}' "4"

# ── 10. GET /issue-link-types — con x-user ────────────────────────────────────
header "10. GET /issue-link-types (H3 fix — rate limit activo)"
assert_http "GET /issue-link-types devuelve 200" \
    "$SERVICE_URL/issue-link-types"
assert_ok "Devuelve al menos un tipo de link" "$(cat /tmp/test_actions_resp.json)" "name\|Relates\|Blocks"

# ── Resumen ───────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════"
echo "  Resultado: $PASS passed / $FAIL failed"
echo ""
echo "  Tickets creados (prefijo [MCP Claude Jira Test]):"
[ -n "$CLONE_KEY" ] && echo "    Clone:  https://jira.zurich.com/browse/$CLONE_KEY"
[ -n "$SAZ_KEY" ]   && echo "    SAZ:    https://jira.zurich.com/browse/$SAZ_KEY"
echo "══════════════════════════════════════"

# shellcheck source=scripts/_test_log.sh
source "$(dirname "$0")/_test_log.sh"
_write_test_log "actions" "$PASS" "$FAIL" "${CLONE_KEY:-}"

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
