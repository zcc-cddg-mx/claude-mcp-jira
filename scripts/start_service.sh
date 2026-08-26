#!/usr/bin/env bash
# start_service.sh — wrapper para systemd.
# Carga .env, aplica overrides WSL, arranca service (:18000) + MCP (:18001).
# Si cualquiera de los dos muere, sale para que systemd reinicie el stack completo.
set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

# ── variables de entorno ────────────────────────────────────────────────────
set -a
[ -f "$REPO_DIR/.env" ] && source "$REPO_DIR/.env"
set +a

# Overrides específicos para WSL / dev local
export REQUESTS_CA_BUNDLE="/etc/ssl/certs/ca-certificates.crt"
export AUDIT_LOG_PATH="/tmp/mcp-jira-audit.log"
export SERVICE_URL="http://localhost:18000"
export APP_ENV="dev"
export MCP_PORT=18001
export JIRA_TIMEOUT=30

# ── resolver conda env ──────────────────────────────────────────────────────
# Reutiliza la misma lógica de resolución que dev.sh
source "$REPO_DIR/scripts/_conda_env.sh"

SERVICE_PORT=18000
MCP_PORT_NUM=18001

# ── liberar puertos si están ocupados ──────────────────────────────────────
_free_port() {
    local port=$1
    local pids
    pids=$(ss -tlnp "sport = :$port" 2>/dev/null \
        | awk 'NR>1 {match($0,/pid=([0-9]+)/,a); if(a[1]) print a[1]}')
    for pid in $pids; do
        echo "[start_service] liberando puerto $port (PID $pid)"
        kill -TERM "$pid" 2>/dev/null || true
    done
}
_free_port $SERVICE_PORT
_free_port $MCP_PORT_NUM
sleep 0.5

# ── arrancar procesos ───────────────────────────────────────────────────────
echo "[start_service] arrancando service layer en :$SERVICE_PORT"
"$UVICORN" service.main:app \
    --host 127.0.0.1 --port $SERVICE_PORT \
    --log-level info \
    >> /tmp/mcp-jira-service.log 2>&1 &
SERVICE_PID=$!

echo "[start_service] arrancando MCP server en :$MCP_PORT_NUM"
"$UVICORN" jira_mcp.server:app \
    --host 127.0.0.1 --port $MCP_PORT_NUM \
    --log-level info \
    >> /tmp/mcp-jira-mcp.log 2>&1 &
MCP_PID=$!

echo "[start_service] service PID=$SERVICE_PID  mcp PID=$MCP_PID"

# ── apagado limpio (SIGTERM desde systemd) ──────────────────────────────────
_cleanup() {
    echo "[start_service] deteniendo servicios (PID $SERVICE_PID $MCP_PID)..."
    kill "$SERVICE_PID" "$MCP_PID" 2>/dev/null || true
    wait "$SERVICE_PID" "$MCP_PID" 2>/dev/null || true
    echo "[start_service] detenido."
}
trap _cleanup SIGTERM SIGINT

# ── mantener vivo; salir si cualquiera muere (systemd reiniciará) ───────────
wait -n "$SERVICE_PID" "$MCP_PID" 2>/dev/null || true
echo "[start_service] un proceso terminó — saliendo para reinicio de systemd"
kill "$SERVICE_PID" "$MCP_PID" 2>/dev/null || true
wait "$SERVICE_PID" "$MCP_PID" 2>/dev/null || true
