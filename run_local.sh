#!/usr/bin/env bash
# Arranca el stack completo (service :18000 + MCP :18001) en modo desarrollo local.
# Sobreescribe las rutas Docker del .env con valores correctos para WSL/local.
#
# Uso:
#   bash run_local.sh          # levantar ambos servicios
#   bash run_local.sh stop     # detener
#   bash run_local.sh restart  # reiniciar
#   bash run_local.sh status   # ver estado
#   bash run_local.sh logs     # tail de logs en tiempo real

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$REPO_DIR/.env"

# ── Cargar .env para tener acceso a variables como TOKEN_AZURE, JIRA_PAT, etc. ──
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

# ── Overrides locales — rutas que difieren entre Docker y WSL/local ──
# Usar el bundle del sistema (DigiCert — jira.zurich.com no pasa por proxy SSL desde WSL)
export REQUESTS_CA_BUNDLE="/etc/ssl/certs/ca-certificates.crt"
export AUDIT_LOG_PATH="/tmp/mcp-jira-audit.log"
export SERVICE_URL="http://localhost:18000"
export APP_ENV="dev"
export PROJECT_DB_PATH="$REPO_DIR/projects.db"

exec bash "$REPO_DIR/scripts/dev.sh" "${1:-both}"
