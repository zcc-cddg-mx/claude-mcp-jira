#!/usr/bin/env bash
# Test runner — validación end-to-end de multi-proyecto (Fases 7 y 7b).
# Asume que el service layer ya está corriendo en :18000 (usa --no-restart por defecto).
# Uso: bash scripts/test-multi.sh [--restart]

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=scripts/_conda_env.sh
source "$(dirname "$0")/_conda_env.sh"
SERVICE_PORT="${MCP_SERVICE_PORT:-18000}"
SERVICE_URL="${MCP_SERVICE_BASE_URL:-http://localhost:$SERVICE_PORT}"
PIDFILE=/tmp/mcp-jira-service.pid
LOG_SERVICE=/tmp/mcp-jira-service.log
CLI="$PYTHON $REPO_DIR/cli/main.py"
PASS=0
FAIL=0
RESTART=0

[ "$1" = "--restart" ] && RESTART=1

export SERVICE_URL
export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
export AUDIT_LOG_PATH=/tmp/audit.log
export JIRA_TIMEOUT=30

cd "$REPO_DIR"

green()  { echo -e "\033[32m✓ $*\033[0m"; }
red()    { echo -e "\033[31m✗ $*\033[0m"; }
yellow() { echo -e "\033[33m~ $*\033[0m"; }
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
        code=$(curl -s -o /tmp/test_multi_resp.json -w "%{http_code}" \
            -X "$method" "$url" \
            -H "Content-Type: application/json" \
            -H "x-user: carlos.duarte2" \
            -d "$body")
    else
        code=$(curl -s -o /tmp/test_multi_resp.json -w "%{http_code}" \
            -H "x-user: carlos.duarte2" "$url")
    fi
    local first_digit="${code:0:1}"
    if [ "$first_digit" = "$expected_code" ]; then
        green "$desc (HTTP $code)"
        PASS=$((PASS+1))
    else
        red "$desc (esperado ${expected_code}xx, obtuvo HTTP $code)"
        cat /tmp/test_multi_resp.json
        FAIL=$((FAIL+1))
    fi
    cat /tmp/test_multi_resp.json
    echo ""
}

kill_port() {
    local port=$1
    local pids
    pids=$(ss -tlnp "sport = :$port" 2>/dev/null | awk 'NR>1 {match($0,/pid=([0-9]+)/,a); if(a[1]) print a[1]}')
    for pid in $pids; do
        echo "[setup] Liberando puerto $port (PID $pid)"
        kill -TERM "$pid" 2>/dev/null || true
    done
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
        sleep 0.5
        echo -n "."
    done
    echo " TIMEOUT"
    return 1
}

# ── 0. Setup ─────────────────────────────────────────────────────────────────
header "0. Setup: service layer"

if [ "$RESTART" -eq 1 ]; then
    echo "[setup] Reiniciando service layer..."
    if [ -f "$PIDFILE" ]; then
        pid=$(cat "$PIDFILE")
        kill -TERM "$pid" 2>/dev/null || true
        rm -f "$PIDFILE"
        sleep 0.5
    fi
    kill_port $SERVICE_PORT
    sleep 0.5
    nohup "$UVICORN" service.main:app --port $SERVICE_PORT --host 127.0.0.1 \
        > "$LOG_SERVICE" 2>&1 &
    echo $! > "$PIDFILE"
    echo "[setup] Nuevo PID: $(cat $PIDFILE)"
    if ! wait_port $SERVICE_PORT; then
        red "No se pudo levantar el service layer. Revisa $LOG_SERVICE"
        exit 1
    fi
else
    if ! curl -sf "$SERVICE_URL/health" > /dev/null 2>&1; then
        red "Service layer no responde en $SERVICE_URL — usa --restart o arranca con: bash scripts/dev.sh service"
        exit 1
    fi
    echo "[setup] Usando service layer existente en $SERVICE_URL"
fi

green "Service layer activo"

# ── 1. GET /projects — proyectos seeded al startup ────────────────────────────
header "1. GET /projects — seed ZNRX / AIPROJECTS / SCRX"
assert_http "GET /projects devuelve 200" "$SERVICE_URL/projects"
output=$(cat /tmp/test_multi_resp.json)
assert_ok "Respuesta contiene ZNRX" "$output" "ZNRX"
assert_ok "Respuesta contiene AIPROJECTS" "$output" "AIPROJECTS"
assert_ok "Respuesta contiene SCRX" "$output" "SCRX"

# ── 2. GET /projects/{key} — proyecto seeded ─────────────────────────────────
header "2. GET /projects/ZNRX — config curada"
assert_http "GET /projects/ZNRX devuelve 200" "$SERVICE_URL/projects/ZNRX"
output=$(cat /tmp/test_multi_resp.json)
assert_ok "priority_format = id" "$output" "\"priority_format\":\"id\""
assert_ok "discovery_source = seed" "$output" "seed"

# ── 3. GET /projects/{key} — auto-discovery SAZ ───────────────────────────────
header "3. GET /projects/SAZ — auto-discovery (no está seeded)"
assert_http "GET /projects/SAZ devuelve 200" "$SERVICE_URL/projects/SAZ"
output=$(cat /tmp/test_multi_resp.json)
assert_ok "Respuesta contiene SAZ" "$output" "SAZ"
assert_ok "discovery_source = jira_auto" "$output" "jira_auto"

# ── 4. GET /projects/{key} — proyecto inexistente ────────────────────────────
header "4. GET /projects/NOEXISTE — debe devolver 404"
assert_http "GET /projects/NOEXISTE devuelve 404" \
    "$SERVICE_URL/projects/NOEXISTE" GET "" "4"

# ── 5. Crear ticket en AIPROJECTS ─────────────────────────────────────────────
header "5. POST /issues con project=AIPROJECTS"
CREATED_AI=""
resp=$(curl -s -X POST "$SERVICE_URL/issues" \
    -H "Content-Type: application/json" \
    -H "x-user: carlos.duarte2" \
    -d '{"text": "[MCP Claude Jira Test] multi-project test — AIPROJECTS ticket, puede eliminarse", "project": "AIPROJECTS"}')
echo "$resp"
echo ""
http_ok=$(echo "$resp" | grep -c '"status"')
if echo "$resp" | grep -qi "AIPROJECTS-"; then
    CREATED_AI=$(echo "$resp" | grep -oE 'AIPROJECTS-[0-9]+' | head -1)
    green "Ticket creado en AIPROJECTS: $CREATED_AI"
    PASS=$((PASS+1))
else
    red "Respuesta no contiene key AIPROJECTS-XXX"
    FAIL=$((FAIL+1))
fi

# ── 6. Crear ticket sin project — debe usar JIRA_DEFAULT_PROJECT ──────────────
header "6. POST /issues sin project — usa default (ZNRX)"
CREATED_DEFAULT=""
resp=$(curl -s -X POST "$SERVICE_URL/issues" \
    -H "Content-Type: application/json" \
    -H "x-user: carlos.duarte2" \
    -d '{"text": "[MCP Claude Jira Test] multi-project test — default project ticket, puede eliminarse"}')
echo "$resp"
echo ""
if echo "$resp" | grep -qi "ZNRX-"; then
    CREATED_DEFAULT=$(echo "$resp" | grep -oE 'ZNRX-[0-9]+' | head -1)
    green "Ticket creado en proyecto default (ZNRX): $CREATED_DEFAULT"
    PASS=$((PASS+1))
else
    red "Respuesta no contiene key ZNRX-XXX"
    FAIL=$((FAIL+1))
fi

# ── 7. Buscar en AIPROJECTS — JQL debe incluir project = "AIPROJECTS" ─────────
header "7. POST /issues/search con project=AIPROJECTS"
assert_http "POST /issues/search con project=AIPROJECTS devuelve 200" \
    "$SERVICE_URL/issues/search" POST \
    '{"query": "tareas abiertas", "project": "AIPROJECTS"}'
output=$(cat /tmp/test_multi_resp.json)
assert_ok "Búsqueda en AIPROJECTS devuelve respuesta válida (total puede ser 0)" "$output" "total"

# ── 8. Buscar sin project — usa default ZNRX ─────────────────────────────────
header "8. POST /issues/search sin project — usa default"
assert_http "POST /issues/search sin project devuelve 200" \
    "$SERVICE_URL/issues/search" POST \
    '{"query": "tareas abiertas"}'
output=$(cat /tmp/test_multi_resp.json)
assert_ok "Resultados contienen issues (total o items)" "$output" "total\|items\|ZNRX"

# ── 9. CLI --project flag ─────────────────────────────────────────────────────
header "9. CLI create --project AIPROJECTS"
CREATED_CLI_AI=""
output=$($CLI create "[MCP Claude Jira Test] CLI multi-project test, puede eliminarse" --project AIPROJECTS 2>&1)
echo "$output"
if echo "$output" | grep -qi "AIPROJECTS-"; then
    CREATED_CLI_AI=$(echo "$output" | grep -oE 'AIPROJECTS-[0-9]+' | head -1)
    green "CLI --project AIPROJECTS creó: $CREATED_CLI_AI"
    PASS=$((PASS+1))
else
    red "CLI --project AIPROJECTS no devolvió key AIPROJECTS-XXX"
    FAIL=$((FAIL+1))
fi

# ── 10. Proyecto fuera de allowlist (si JIRA_ALLOWED_PROJECTS está configurado) ─
header "10. POST /issues con proyecto fuera de allowlist"
yellow "Este test solo falla si JIRA_ALLOWED_PROJECTS está configurado y excluye FAKEPRO"
resp_code=$(curl -s -o /tmp/test_multi_resp.json -w "%{http_code}" \
    -X POST "$SERVICE_URL/issues" \
    -H "Content-Type: application/json" \
    -H "x-user: carlos.duarte2" \
    -d '{"text": "test allowlist", "project": "FAKEPRO"}')
echo "HTTP $resp_code — $(cat /tmp/test_multi_resp.json)"
echo ""
if [ "$resp_code" = "400" ] || [ "$resp_code" = "404" ]; then
    green "FAKEPRO rechazado correctamente (HTTP $resp_code)"
    PASS=$((PASS+1))
else
    yellow "FAKEPRO devolvió HTTP $resp_code (puede ser correcto si JIRA_ALLOWED_PROJECTS está vacío)"
    # No contamos como fallo — comportamiento depende de la config
fi

# ── Resumen ───────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════"
echo "  Resultado: $PASS passed / $FAIL failed"
echo ""
echo "  Tickets creados (prefijo [MCP Claude Jira Test]):"
[ -n "$CREATED_AI" ]      && echo "    AIPROJECTS (API):  https://jira.zurich.com/browse/$CREATED_AI"
[ -n "$CREATED_DEFAULT" ] && echo "    ZNRX (default):    https://jira.zurich.com/browse/$CREATED_DEFAULT"
[ -n "$CREATED_CLI_AI" ]  && echo "    AIPROJECTS (CLI):  https://jira.zurich.com/browse/$CREATED_CLI_AI"
echo "══════════════════════════════════════"

# shellcheck source=scripts/_test_log.sh
source "$(dirname "$0")/_test_log.sh"
_write_test_log "multi" "$PASS" "$FAIL" "${CREATED_AI:-${CREATED_DEFAULT:-}}"

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
