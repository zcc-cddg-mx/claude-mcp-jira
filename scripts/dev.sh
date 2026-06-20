#!/usr/bin/env bash
# Script de arranque para desarrollo local (fuera de Docker)
# Uso: bash scripts/dev.sh [service|mcp|both]
#
# Diferencias vs producción Docker:
#   - PORT: 18000 (8000 ocupado por Portainer)
#   - REQUESTS_CA_BUNDLE: bundle del sistema (DigiCert — jira.zurich.com no usa proxy de inspección SSL desde WSL)
#   - AUDIT_LOG_PATH: /tmp/audit.log
#   - SERVICE_URL: http://localhost:18000

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
UVICORN="/home/idavid/miniconda3/envs/claude-mcp-jira/bin/uvicorn"
PYTHON="/home/idavid/miniconda3/envs/claude-mcp-jira/bin/python"

export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
export AUDIT_LOG_PATH=/tmp/audit.log
export SERVICE_URL=http://localhost:18000

cd "$REPO_DIR"

MODE="${1:-service}"

start_service() {
    echo "[dev] Arrancando service layer en :18000"
    echo "[dev] REQUESTS_CA_BUNDLE=$REQUESTS_CA_BUNDLE"
    echo "[dev] AUDIT_LOG_PATH=$AUDIT_LOG_PATH"
    "$UVICORN" service.main:app --port 18000 --host 127.0.0.1 --reload
}

start_mcp() {
    echo "[dev] Arrancando MCP server en :18001"
    "$PYTHON" -m mcp.server
}

case "$MODE" in
    service) start_service ;;
    mcp)     start_mcp ;;
    both)
        start_service &
        SERVICE_PID=$!
        sleep 3
        start_mcp &
        MCP_PID=$!
        trap "kill $SERVICE_PID $MCP_PID 2>/dev/null" EXIT
        wait
        ;;
    *)
        echo "Uso: $0 [service|mcp|both]"
        exit 1
        ;;
esac
