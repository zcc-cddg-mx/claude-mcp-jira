#!/usr/bin/env bash
# Helper compartido: escribe una entrada JSONL al log de ejecuciones de test.
# Uso: _write_test_log <suite> <pass> <fail> [ticket_key]
#
# Llamado al final de test-dev.sh y test-mcp.sh.
# El log se guarda en logs/test-results.jsonl (ignorado por git).

_write_test_log() {
    local suite="$1"
    local pass="$2"
    local fail="$3"
    local ticket="${4:-}"
    local env="${MCP_TEST_ENV:-dev}"

    local repo_dir
    repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
    local log_dir="$repo_dir/logs"
    local log_file="$log_dir/test-results.jsonl"

    mkdir -p "$log_dir"

    local status="passed"
    [ "$fail" -gt 0 ] && status="failed"

    local commit
    commit=$(git -C "$repo_dir" rev-parse --short HEAD 2>/dev/null || echo "unknown")

    local branch
    branch=$(git -C "$repo_dir" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Construir JSON manualmente (sin dependencias externas)
    local entry="{\"timestamp\":\"$timestamp\",\"suite\":\"$suite\",\"env\":\"$env\",\"status\":\"$status\",\"passed\":$pass,\"failed\":$fail,\"commit\":\"$commit\",\"branch\":\"$branch\""
    [ -n "$ticket" ] && entry="$entry,\"ticket\":\"$ticket\""
    entry="$entry}"

    echo "$entry" >> "$log_file"
    echo "[test-log] → $log_file"
}
