#!/usr/bin/env bash
# Arranca el stack completo en modo desarrollo local:
#   - code-agent-mcp   :5001  (/home/idavid/dev/claude/code-agent-mcp)
#   - service layer    :18000
#   - MCP server       :18001
#
# Uso:
#   bash run_local.sh          # levantar los tres servicios
#   bash run_local.sh stop     # detener los tres
#   bash run_local.sh restart  # reiniciar los tres
#   bash run_local.sh status   # ver estado de los tres
#   bash run_local.sh logs     # tail de todos los logs

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
CODE_AGENT_DIR="/home/idavid/dev/claude/code-agent-mcp"
ENV_FILE="$REPO_DIR/.env"

LOG_CODE_AGENT="/tmp/code-agent-mcp.log"
PIDFILE_CODE_AGENT="/tmp/code-agent-mcp.pid"
CODE_AGENT_PORT=5001

# ── Cargar .env para tener acceso a TOKEN_AZURE, JIRA_PAT, MCP_API_KEY, etc. ──
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

# ── Overrides locales — rutas que difieren entre Docker y WSL/local ──
export REQUESTS_CA_BUNDLE="/etc/ssl/certs/ca-certificates.crt"
export AUDIT_LOG_PATH="/tmp/mcp-jira-audit.log"
export SERVICE_URL="http://localhost:18000"
export APP_ENV="dev"
export PROJECT_DB_PATH="$REPO_DIR/projects.db"

# ── helpers code-agent ────────────────────────────────────────────────────────

start_code_agent() {
    # Matar proceso existente en el puerto
    local pids
    pids=$(ss -tlnp "sport = :$CODE_AGENT_PORT" 2>/dev/null \
        | awk 'NR>1 {match($0,/pid=([0-9]+)/,a); if(a[1]) print a[1]}')
    for pid in $pids; do
        echo "[run_local] Liberando puerto $CODE_AGENT_PORT (PID $pid)"
        kill -TERM "$pid" 2>/dev/null || true
        sleep 1
    done

    echo "[run_local] Arrancando code-agent-mcp en :$CODE_AGENT_PORT — log: $LOG_CODE_AGENT"
    nohup bash "$CODE_AGENT_DIR/run_local.sh" > "$LOG_CODE_AGENT" 2>&1 &
    echo $! > "$PIDFILE_CODE_AGENT"

    echo -n "[run_local] Esperando code-agent-mcp en :$CODE_AGENT_PORT ..."
    for i in $(seq 1 20); do
        ss -tlnp "sport = :$CODE_AGENT_PORT" 2>/dev/null | grep -q ":$CODE_AGENT_PORT" \
            && { echo " listo."; return 0; }
        sleep 0.5
        echo -n "."
    done
    echo " TIMEOUT — revisa $LOG_CODE_AGENT"
    return 1
}

stop_code_agent() {
    if [ -f "$PIDFILE_CODE_AGENT" ]; then
        local pid
        pid=$(cat "$PIDFILE_CODE_AGENT")
        echo "[run_local] Deteniendo code-agent-mcp (PID $pid)"
        kill -TERM "$pid" 2>/dev/null || true
        rm -f "$PIDFILE_CODE_AGENT"
    fi
    local pids
    pids=$(ss -tlnp "sport = :$CODE_AGENT_PORT" 2>/dev/null \
        | awk 'NR>1 {match($0,/pid=([0-9]+)/,a); if(a[1]) print a[1]}')
    for pid in $pids; do kill -TERM "$pid" 2>/dev/null || true; done
}

status_code_agent() {
    echo "[run_local] code-agent-mcp (:$CODE_AGENT_PORT):"
    ss -tlnp "sport = :$CODE_AGENT_PORT" 2>/dev/null | grep -q ":$CODE_AGENT_PORT" \
        && echo "  ✓ activo" || echo "  ✗ detenido"
}

# ── main ──────────────────────────────────────────────────────────────────────

MODE="${1:-both}"

case "$MODE" in
    stop)
        stop_code_agent
        bash "$REPO_DIR/scripts/dev.sh" stop
        ;;
    status)
        status_code_agent
        bash "$REPO_DIR/scripts/dev.sh" status
        ;;
    restart)
        stop_code_agent
        bash "$REPO_DIR/scripts/dev.sh" stop
        sleep 1
        start_code_agent
        bash "$REPO_DIR/scripts/dev.sh" both
        echo "[run_local] Stack completo reiniciado."
        ;;
    logs)
        tail -f "$LOG_CODE_AGENT" /tmp/mcp-jira-service.log /tmp/mcp-jira-mcp.log
        ;;
    both|*)
        start_code_agent
        exec bash "$REPO_DIR/scripts/dev.sh" both
        ;;
esac
