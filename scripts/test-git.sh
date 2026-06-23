#!/usr/bin/env bash
# Test runner — validación e2e de Git Intelligence (Fase 9).
# Cubre: POST/GET/DELETE /git/repos (CRUD registry) + POST /git/sync (dry_run).
# Asume service layer corriendo en :18000. Uso: bash scripts/test-git.sh [--restart]

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

# Repo real de este proyecto — siempre disponible en dev
THIS_REPO_PATH="$REPO_DIR"
TEST_ALIAS="test-git-e2e-$$"

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
        code=$(curl -s -o /tmp/test_git_resp.json -w "%{http_code}" \
            -X "$method" "$url" \
            -H "Content-Type: application/json" \
            -H "x-user: carlos.duarte2" \
            -d "$body")
    else
        code=$(curl -s -o /tmp/test_git_resp.json -w "%{http_code}" \
            -X "$method" "$url" \
            -H "x-user: carlos.duarte2")
    fi
    local first_digit="${code:0:1}"
    if [ "$first_digit" = "$expected_code" ]; then
        green "$desc (HTTP $code)"
        PASS=$((PASS+1))
    else
        red "$desc (esperado ${expected_code}xx, obtuvo HTTP $code)"
        cat /tmp/test_git_resp.json
        FAIL=$((FAIL+1))
    fi
    cat /tmp/test_git_resp.json
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

# ── 0. Setup ──────────────────────────────────────────────────────────────────
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

# Limpiar alias de test previo si quedó de una ejecución anterior
curl -s -o /dev/null -X DELETE "$SERVICE_URL/git/repos/$TEST_ALIAS" -H "x-user: carlos.duarte2" 2>/dev/null || true
green "Service layer activo — alias de test: $TEST_ALIAS"

# ── 1. POST /git/repos — registrar repo ──────────────────────────────────────
header "1. POST /git/repos — registrar repo"
assert_http "Registrar repo con alias $TEST_ALIAS" \
    "$SERVICE_URL/git/repos" POST \
    "{\"name\": \"$TEST_ALIAS\", \"repo_path\": \"$THIS_REPO_PATH\", \"jira_project\": \"AIPROJECTS\", \"default_issue_key\": \"AIPROJECTS-47\"}" "2"
assert_ok "Respuesta contiene alias" "$(cat /tmp/test_git_resp.json)" "$TEST_ALIAS"
assert_ok "Respuesta contiene repo_path" "$(cat /tmp/test_git_resp.json)" "$THIS_REPO_PATH"

# ── 2. GET /git/repos — listar repos ─────────────────────────────────────────
header "2. GET /git/repos — listar repos"
assert_http "Listar repos" "$SERVICE_URL/git/repos" GET
assert_ok "Respuesta contiene repos array" "$(cat /tmp/test_git_resp.json)" "repos\|total"
assert_ok "Lista contiene el alias registrado" "$(cat /tmp/test_git_resp.json)" "$TEST_ALIAS"

# ── 3. GET /git/repos/{name} — obtener repo por alias ────────────────────────
header "3. GET /git/repos/{name} — obtener por alias"
assert_http "Obtener repo $TEST_ALIAS" "$SERVICE_URL/git/repos/$TEST_ALIAS" GET
assert_ok "Respuesta contiene jira_project" "$(cat /tmp/test_git_resp.json)" "AIPROJECTS"
assert_ok "Respuesta contiene default_issue_key" "$(cat /tmp/test_git_resp.json)" "AIPROJECTS-47"

# ── 4. GET /git/repos/{name} — alias inexistente → 404 ───────────────────────
header "4. GET /git/repos/{name} — alias inexistente"
assert_http "Alias no registrado devuelve 404" \
    "$SERVICE_URL/git/repos/repo-que-no-existe-xyz" GET "" "4"
assert_ok "Mensaje de error correcto" "$(cat /tmp/test_git_resp.json)" "no encontrado\|not found\|404"

# ── 5. POST /git/repos — ruta no absoluta → 422 ──────────────────────────────
header "5. POST /git/repos — validación ruta absoluta"
assert_http "repo_path relativo devuelve 422" \
    "$SERVICE_URL/git/repos" POST \
    '{"name": "repo-relativo", "repo_path": "ruta/relativa/repo"}' "4"

# ── 6. POST /git/sync — dry_run por repo_path ────────────────────────────────
header "6. POST /git/sync — dry_run con repo_path"
assert_http "dry_run sobre este repo con repo_path" \
    "$SERVICE_URL/git/sync" POST \
    "{\"repo_path\": \"$THIS_REPO_PATH\", \"dry_run\": true, \"since_days\": 7}"
assert_ok "Respuesta contiene dry_run=true" "$(cat /tmp/test_git_resp.json)" "dry_run\|sessions\|total_commits"
assert_ok "Respuesta contiene repo_path" "$(cat /tmp/test_git_resp.json)" "$THIS_REPO_PATH"

# ── 7. POST /git/sync — dry_run por repo_name (alias) ────────────────────────
header "7. POST /git/sync — dry_run con repo_name"
assert_http "dry_run con alias $TEST_ALIAS" \
    "$SERVICE_URL/git/sync" POST \
    "{\"repo_name\": \"$TEST_ALIAS\", \"dry_run\": true, \"since_days\": 7}"
assert_ok "Respuesta contiene sessions" "$(cat /tmp/test_git_resp.json)" "sessions"
assert_ok "Respuesta contiene repo_path resuelto" "$(cat /tmp/test_git_resp.json)" "$THIS_REPO_PATH"

# ── 8. POST /git/sync — repo_name inexistente → 404 ──────────────────────────
header "8. POST /git/sync — repo_name inexistente"
assert_http "repo_name no registrado devuelve 404" \
    "$SERVICE_URL/git/sync" POST \
    '{"repo_name": "alias-que-no-existe-xyz", "dry_run": true}' "4"
assert_ok "Mensaje de error sobre registro" "$(cat /tmp/test_git_resp.json)" "registrado\|no registrado\|not found"

# ── 9. POST /git/sync — ruta no absoluta → 422 ───────────────────────────────
header "9. POST /git/sync — validación ruta absoluta"
assert_http "repo_path relativo en sync devuelve 422" \
    "$SERVICE_URL/git/sync" POST \
    '{"repo_path": "ruta/relativa", "dry_run": true}' "4"

# ── 10. POST /git/repos — actualizar alias (upsert) ──────────────────────────
header "10. POST /git/repos — actualizar repo existente (upsert)"
assert_http "Re-registrar $TEST_ALIAS con nueva default_issue_key" \
    "$SERVICE_URL/git/repos" POST \
    "{\"name\": \"$TEST_ALIAS\", \"repo_path\": \"$THIS_REPO_PATH\", \"default_issue_key\": \"AIPROJECTS-48\"}" "2"
assert_ok "Nueva default_issue_key reflejada" "$(cat /tmp/test_git_resp.json)" "AIPROJECTS-48"

# ── 11. DELETE /git/repos/{name} — eliminar alias ────────────────────────────
header "11. DELETE /git/repos/{name} — eliminar alias"
assert_http "Eliminar alias $TEST_ALIAS devuelve 204" \
    "$SERVICE_URL/git/repos/$TEST_ALIAS" DELETE "" "2"

# ── 12. GET /git/repos/{name} — ya no debe existir ───────────────────────────
header "12. GET tras DELETE — alias ya no existe"
assert_http "Alias eliminado devuelve 404" \
    "$SERVICE_URL/git/repos/$TEST_ALIAS" GET "" "4"

# ── 13. DELETE /git/repos/{name} — alias inexistente → 404 ───────────────────
header "13. DELETE /git/repos/{name} — alias inexistente"
assert_http "DELETE de alias no existente devuelve 404" \
    "$SERVICE_URL/git/repos/$TEST_ALIAS" DELETE "" "4"

# ── Resumen ───────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════"
echo "  Resultado: $PASS passed / $FAIL failed"
echo "══════════════════════════════════════"

# shellcheck source=scripts/_test_log.sh
source "$(dirname "$0")/_test_log.sh"
_write_test_log "git" "$PASS" "$FAIL"

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
