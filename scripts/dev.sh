#!/usr/bin/env bash
# Script de arranque para desarrollo local (fuera de Docker).
# Uso: bash scripts/dev.sh [service|mcp|both|stop]
#
# Diferencias vs producción Docker:
#   - PORT service: 18000 (8000 ocupado por Portainer)
#   - PORT mcp:     18001
#   - REQUESTS_CA_BUNDLE: bundle del sistema (DigiCert — jira.zurich.com no usa proxy SSL desde WSL)
#   - AUDIT_LOG_PATH: /tmp/audit.log
#   - SERVICE_URL: http://localhost:18000

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONDA_ENV="/home/idavid/miniconda3/envs/claude-mcp-jira"
UVICORN="$CONDA_ENV/bin/uvicorn"
PYTHON="$CONDA_ENV/bin/python"

SERVICE_PORT=18000
MCP_PORT=18001
PIDFILE_SERVICE=/tmp/mcp-jira-service.pid
PIDFILE_MCP=/tmp/mcp-jira-mcp.pid
LOG_SERVICE=/tmp/mcp-jira-service.log
LOG_MCP=/tmp/mcp-jira-mcp.log

export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
export AUDIT_LOG_PATH=/tmp/audit.log
export SERVICE_URL=http://localhost:$SERVICE_PORT
export MCP_PORT=$MCP_PORT
export JIRA_TIMEOUT=30

cd "$REPO_DIR"

# ── helpers ──────────────────────────────────────────────────────────────────

kill_port() {
    local port=$1
    local pids
    pids=$(ss -tlnp "sport = :$port" 2>/dev/null | awk 'NR>1 {match($0,/pid=([0-9]+)/,a); if(a[1]) print a[1]}')
    for pid in $pids; do
        echo "[dev] Liberando puerto $port (PID $pid)"
        kill -TERM "$pid" 2>/dev/null || true
    done
    # Esperar que libere
    for i in $(seq 1 10); do
        ss -tlnp "sport = :$port" 2>/dev/null | grep -q ":$port" || return 0
        sleep 0.5
    done
    echo "[dev] Forzando SIGKILL en puerto $port"
    pids=$(ss -tlnp "sport = :$port" 2>/dev/null | awk 'NR>1 {match($0,/pid=([0-9]+)/,a); if(a[1]) print a[1]}')
    for pid in $pids; do kill -9 "$pid" 2>/dev/null || true; done
}

kill_by_pidfile() {
    local pidfile=$1
    if [ -f "$pidfile" ]; then
        local pid
        pid=$(cat "$pidfile")
        echo "[dev] Deteniendo PID $pid ($(basename $pidfile))"
        kill -TERM "$pid" 2>/dev/null || true
        rm -f "$pidfile"
    fi
}

stop_all() {
    kill_by_pidfile "$PIDFILE_SERVICE"
    kill_by_pidfile "$PIDFILE_MCP"
    kill_port $SERVICE_PORT
    kill_port $MCP_PORT
    echo "[dev] Servicios detenidos."
}

wait_port() {
    local port=$1 name=$2
    echo -n "[dev] Esperando $name en :$port ..."
    for i in $(seq 1 20); do
        ss -tlnp "sport = :$port" 2>/dev/null | grep -q ":$port" && { echo " listo."; return 0; }
        sleep 0.5
        echo -n "."
    done
    echo " TIMEOUT"
    return 1
}

start_service() {
    kill_port $SERVICE_PORT
    echo "[dev] Arrancando service layer en :$SERVICE_PORT — log: $LOG_SERVICE"
    nohup "$UVICORN" service.main:app --port $SERVICE_PORT --host 127.0.0.1 \
        > "$LOG_SERVICE" 2>&1 &
    echo $! > "$PIDFILE_SERVICE"
    wait_port $SERVICE_PORT "service"
}

start_mcp() {
    kill_port $MCP_PORT
    echo "[dev] Arrancando MCP server en :$MCP_PORT — log: $LOG_MCP"
    nohup "$PYTHON" -m mcp.server \
        > "$LOG_MCP" 2>&1 &
    echo $! > "$PIDFILE_MCP"
    wait_port $MCP_PORT "mcp"
}

status() {
    echo "[dev] Service layer (:$SERVICE_PORT):"
    ss -tlnp "sport = :$SERVICE_PORT" 2>/dev/null | grep -q ":$SERVICE_PORT" \
        && echo "  ✓ activo" || echo "  ✗ detenido"
    echo "[dev] MCP server (:$MCP_PORT):"
    ss -tlnp "sport = :$MCP_PORT" 2>/dev/null | grep -q ":$MCP_PORT" \
        && echo "  ✓ activo" || echo "  ✗ detenido"
}

# ── main ─────────────────────────────────────────────────────────────────────

MODE="${1:-service}"

case "$MODE" in
    service)
        start_service
        tail -f "$LOG_SERVICE"
        ;;
    mcp)
        start_mcp
        tail -f "$LOG_MCP"
        ;;
    both)
        start_service
        start_mcp
        echo "[dev] Ambos servicios activos. Ctrl+C para salir."
        trap "stop_all" INT TERM
        tail -f "$LOG_SERVICE" "$LOG_MCP"
        ;;
    stop)
        stop_all
        ;;
    status)
        status
        ;;
    restart)
        stop_all
        sleep 1
        start_service
        start_mcp
        echo "[dev] Reinicio completo."
        ;;
    *)
        echo "Uso: $0 [service|mcp|both|stop|restart|status]"
        exit 1
        ;;
esac
