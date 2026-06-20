#!/usr/bin/env bash
# Test e2e contra los contenedores Docker (puertos 8000/8001).
# Levanta los contenedores, espera el health, corre test-dev.sh y test-mcp.sh,
# y registra las entradas en logs/test-results.jsonl con env=docker.
# Uso: bash scripts/test-docker.sh [--no-build] [--keep]
#   --no-build  : omite docker compose build (imagen ya existe)
#   --keep      : deja los contenedores corriendo al terminar

set -e
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS="$REPO_DIR/scripts"

SERVICE_URL="http://localhost:8000"
MCP_URL="http://localhost:8001"

NO_BUILD=0
KEEP=0
for arg in "$@"; do
    [ "$arg" = "--no-build" ] && NO_BUILD=1
    [ "$arg" = "--keep" ]     && KEEP=1
done

green()  { echo -e "\033[32m✓ $*\033[0m"; }
red()    { echo -e "\033[31m✗ $*\033[0m"; }
header() { echo -e "\n\033[1m=== $* ===\033[0m"; }

cd "$REPO_DIR"

# ── 1. Build ─────────────────────────────────────────────────────────────────
header "1. Docker build"
if [ "$NO_BUILD" -eq 0 ]; then
    docker compose build
    green "Build OK"
else
    echo "[setup] --no-build: omitiendo build"
fi

# ── 2. Arranque ───────────────────────────────────────────────────────────────
header "2. docker compose up"
docker compose up -d
green "Contenedores arrancados"

# ── 3. Health check con reintentos ────────────────────────────────────────────
header "3. Health check"
echo -n "[setup] Esperando service en $SERVICE_URL ..."
for i in $(seq 1 40); do
    curl -sf "$SERVICE_URL/health" > /dev/null 2>&1 && { echo " listo."; break; }
    [ "$i" -eq 40 ] && { echo " TIMEOUT"; docker compose logs service | tail -20; exit 1; }
    sleep 1; echo -n "."
done
green "Service layer activo"

echo -n "[setup] Esperando MCP en $MCP_URL ..."
for i in $(seq 1 40); do
    curl -sf "$MCP_URL/health" > /dev/null 2>&1 && { echo " listo."; break; }
    [ "$i" -eq 40 ] && { echo " TIMEOUT"; docker compose logs mcp | tail -20; exit 1; }
    sleep 1; echo -n "."
done
green "MCP server activo"

# ── 4. Ejecutar suites apuntando a puertos Docker ─────────────────────────────
header "4. Suite service (→ :8000)"
MCP_TEST_ENV=docker \
MCP_SERVICE_BASE_URL="$SERVICE_URL" \
MCP_SERVICE_PORT=8000 \
    bash "$SCRIPTS/test-dev.sh" --no-restart
SERVICE_RC=$?

header "5. Suite MCP (→ :8001)"
MCP_TEST_ENV=docker \
MCP_SERVICE_BASE_URL="$SERVICE_URL" \
MCP_MCP_BASE_URL="$MCP_URL" \
    bash "$SCRIPTS/test-mcp.sh"
MCP_RC=$?

# ── 5. Teardown ───────────────────────────────────────────────────────────────
if [ "$KEEP" -eq 0 ]; then
    header "6. docker compose down"
    docker compose down
    green "Contenedores detenidos"
else
    echo "[teardown] --keep: contenedores siguen corriendo"
fi

# ── Resultado final ───────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════"
[ "$SERVICE_RC" -eq 0 ] && green "service suite: PASSED" || red "service suite: FAILED"
[ "$MCP_RC" -eq 0 ]     && green "mcp suite:     PASSED" || red "mcp suite:     FAILED"
echo "══════════════════════════════════════"

[ "$SERVICE_RC" -eq 0 ] && [ "$MCP_RC" -eq 0 ] && exit 0 || exit 1
