#!/usr/bin/env bash
# Muestra el historial de ejecuciones de test desde logs/test-results.jsonl
# Uso: bash scripts/test-log.sh [--last N] [--suite service|mcp] [--failures]

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="$REPO_DIR/logs/test-results.jsonl"
# shellcheck source=scripts/_conda_env.sh
source "$(dirname "$0")/_conda_env.sh"

if [ ! -f "$LOG_FILE" ]; then
    echo "Sin historial aún. Ejecuta test-dev.sh o test-mcp.sh primero."
    exit 0
fi

"$PYTHON" - "$LOG_FILE" "$@" <<'EOF'
import json
import sys

log_file = sys.argv[1]
args = sys.argv[2:]

last = 20
suite_filter = None
env_filter = None
only_failures = False

i = 0
while i < len(args):
    if args[i] == "--last" and i + 1 < len(args):
        last = int(args[i + 1]); i += 2
    elif args[i] == "--suite" and i + 1 < len(args):
        suite_filter = args[i + 1]; i += 2
    elif args[i] == "--env" and i + 1 < len(args):
        env_filter = args[i + 1]; i += 2
    elif args[i] == "--failures":
        only_failures = True; i += 1
    else:
        print(f"Uso: test-log.sh [--last N] [--suite service|mcp] [--env dev|docker] [--failures]")
        sys.exit(1)

entries = []
with open(log_file) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            pass

if suite_filter:
    entries = [e for e in entries if e.get("suite") == suite_filter]
if env_filter:
    entries = [e for e in entries if e.get("env", "dev") == env_filter]
if only_failures:
    entries = [e for e in entries if e.get("status") == "failed"]

entries = entries[-last:]

GREEN = "\033[32m"
RED   = "\033[31m"
RESET = "\033[0m"
BOLD  = "\033[1m"

header = f"{BOLD}{'timestamp':<22} {'suite':<8} {'env':<8} {'status':<8} {'pass/fail':<10} {'commit':<8} {'branch':<16} ticket{RESET}"
print(header)
print("─" * 88)

for e in entries:
    color = GREEN if e.get("status") == "passed" else RED
    ticket = e.get("ticket", "-")
    score = f"{e.get('passed',0)}/{e.get('passed',0) + e.get('failed',0)}"
    print(
        f"{e.get('timestamp',''):<22} "
        f"{e.get('suite',''):<8} "
        f"{e.get('env','dev'):<8} "
        f"{color}{e.get('status',''):<8}{RESET} "
        f"{score:<10} "
        f"{e.get('commit',''):<8} "
        f"{e.get('branch',''):<16} "
        f"{ticket}"
    )

print(f"\nMostradas: {len(entries)} | Total en log: ", end="")
with open(log_file) as f:
    print(sum(1 for l in f if l.strip()))
EOF
