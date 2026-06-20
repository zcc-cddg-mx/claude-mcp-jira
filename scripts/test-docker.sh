#!/usr/bin/env bash
# Test e2e contra los contenedores Docker (puertos 18000/18001 en el host).
# Detiene dev mode si está corriendo, levanta Docker, corre ambas suites,
# registra env=docker en logs/test-results.jsonl, y restaura dev al terminar.
# Uso: bash scripts/test-docker.sh [--no-build] [--keep] [--no-dev-restore]
#   --no-build       : omite docker compose build (imagen ya existe)
#   --keep           : deja los contenedores Docker corriendo al terminar
#   --no-dev-restore : no relanzar dev mode al terminar

set -e
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS="$REPO_DIR/scripts"

SERVICE_URL="http://localhost:18000"
MCP_URL="http://localhost:18001"

NO_BUILD=0
KEEP=0
NO_DEV_RESTORE=0
for arg in "$@"; do
    [ "$arg" = "--no-build" ]       && NO_BUILD=1
    [ "$arg" = "--keep" ]           && KEEP=1
    [ "$arg" = "--no-dev-restore" ] && NO_DEV_RESTORE=1
done

green()  { echo -e "\033[32m✓ $*\033[0m"; }
red()    { echo -e "\033[31m✗ $*\033[0m"; }
header() { echo -e "\n\033[1m=== $* ===\033[0m"; }

cd "$REPO_DIR"

# ── 1. Parar dev mode si está corriendo ──────────────────────────────────────
DEV_WAS_RUNNING=0
header "1. Verificar dev mode"
if ss -tlnp 'sport = :18000' 2>/dev/null | grep -q ':18000' || \
   ss -tlnp 'sport = :18001' 2>/dev/null | grep -q ':18001'; then
    echo "[setup] Dev mode corriendo — deteniendo para liberar puertos..."
    bash "$SCRIPTS/dev.sh" stop 2>/dev/null || true
    sleep 1
    DEV_WAS_RUNNING=1
    green "Dev mode detenido"
else
    echo "[setup] Puertos libres"
fi

# Función de cleanup para restaurar dev mode si algo falla
_cleanup() {
    local rc=$?
    if [ "$KEEP" -eq 0 ]; then
        docker compose down 2>/dev/null || true
    fi
    if [ "$DEV_WAS_RUNNING" -eq 1 ] && [ "$NO_DEV_RESTORE" -eq 0 ]; then
        echo "[cleanup] Restaurando dev mode..."
        bash "$SCRIPTS/dev.sh" both 2>/dev/null &
    fi
    exit $rc
}
trap _cleanup ERR INT TERM

# ── 2. Build ─────────────────────────────────────────────────────────────────
header "2. Docker build"
if [ "$NO_BUILD" -eq 0 ]; then
    docker compose build
    green "Build OK"
else
    echo "[setup] --no-build: omitiendo build"
fi

# ── 3. Arranque ───────────────────────────────────────────────────────────────
header "3. docker compose up"
docker compose up -d
green "Contenedores arrancados"

# ── 4. Health check con reintentos ────────────────────────────────────────────
header "4. Health check"
echo -n "[setup] Esperando service en $SERVICE_URL ..."
for i in $(seq 1 40); do
    curl -sf "$SERVICE_URL/health" > /dev/null 2>&1 && { echo " listo."; break; }
    [ "$i" -eq 40 ] && { echo " TIMEOUT"; docker compose logs service | tail -20; exit 1; }
    sleep 1; echo -n "."
done
green "Service layer activo"

echo -n "[setup] Esperando MCP en $MCP_URL ..."
for i in $(seq 1 40); do
    # El MCP no tiene /health — cualquier respuesta HTTP indica que está listo
    code=$(curl -s -o /dev/null -w "%{http_code}" "$MCP_URL/sse" --max-time 2 2>/dev/null || echo "000")
    [ "$code" != "000" ] && { echo " listo (HTTP $code)."; break; }
    [ "$i" -eq 40 ] && { echo " TIMEOUT"; docker compose logs mcp | tail -20; exit 1; }
    sleep 1; echo -n "."
done
green "MCP server activo"

# ── 5. Ejecutar suites apuntando a puertos Docker ─────────────────────────────
header "5. Suite service (→ :18000 Docker)"
MCP_TEST_ENV=docker \
MCP_SERVICE_BASE_URL="$SERVICE_URL" \
MCP_SERVICE_PORT=18000 \
    bash "$SCRIPTS/test-dev.sh" --no-restart
SERVICE_RC=$?

header "6. Suite MCP (→ :18001 Docker)"
MCP_TEST_ENV=docker \
MCP_SERVICE_BASE_URL="$SERVICE_URL" \
MCP_MCP_BASE_URL="$MCP_URL" \
    bash "$SCRIPTS/test-mcp.sh"
MCP_RC=$?

# ── 6. Teardown ───────────────────────────────────────────────────────────────
if [ "$KEEP" -eq 0 ]; then
    header "7. docker compose down"
    docker compose down
    green "Contenedores detenidos"
else
    echo "[teardown] --keep: contenedores siguen corriendo"
fi

# ── 7. Restaurar dev mode ─────────────────────────────────────────────────────
if [ "$DEV_WAS_RUNNING" -eq 1 ] && [ "$NO_DEV_RESTORE" -eq 0 ]; then
    header "8. Restaurar dev mode"
    bash "$SCRIPTS/dev.sh" both
    green "Dev mode restaurado"
fi

trap - ERR INT TERM

# ── Resultado final ───────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════"
[ "$SERVICE_RC" -eq 0 ] && green "service suite: PASSED" || red "service suite: FAILED"
[ "$MCP_RC" -eq 0 ]     && green "mcp suite:     PASSED" || red "mcp suite:     FAILED"
echo "══════════════════════════════════════"

[ "$SERVICE_RC" -eq 0 ] && [ "$MCP_RC" -eq 0 ] && exit 0 || exit 1
