#!/usr/bin/env bash
# Test runner para validación end-to-end en entorno de desarrollo local.
# Requiere service layer corriendo en :18000 (ver scripts/dev.sh).
# Uso: bash scripts/test-dev.sh

set -e

PYTHON="/home/idavid/miniconda3/envs/claude-mcp-jira/bin/python"
SERVICE_URL="http://localhost:18000"
CLI="$PYTHON cli/main.py"
PASS=0
FAIL=0
CREATED_KEY=""

export SERVICE_URL

green()  { echo -e "\033[32m✓ $*\033[0m"; }
red()    { echo -e "\033[31m✗ $*\033[0m"; }
header() { echo -e "\n\033[1m=== $* ===\033[0m"; }

assert_ok() {
    local desc="$1" output="$2" expected="$3"
    if echo "$output" | grep -q "$expected"; then
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
    local desc="$1" url="$2" method="${3:-GET}" body="${4:-}"
    if [ -n "$body" ]; then
        code=$(curl -s -o /tmp/test_response.json -w "%{http_code}" \
            -X "$method" "$url" \
            -H "Content-Type: application/json" \
            -H "x-user: carlos.duarte2" \
            -d "$body")
    else
        code=$(curl -s -o /tmp/test_response.json -w "%{http_code}" "$url")
    fi
    if [ "$code" -ge 200 ] && [ "$code" -lt 300 ]; then
        green "$desc (HTTP $code)"
        PASS=$((PASS+1))
    else
        red "$desc (HTTP $code)"
        cat /tmp/test_response.json
        FAIL=$((FAIL+1))
    fi
    cat /tmp/test_response.json
}

# ── 0. Prerequisito: service layer activo ────────────────────────────────────
header "0. Prerequisito: service layer"
if ! curl -s "$SERVICE_URL/health" | grep -q "ok"; then
    red "Service layer no está corriendo en $SERVICE_URL"
    echo "Ejecuta: bash scripts/dev.sh service"
    exit 1
fi
green "Service layer activo en $SERVICE_URL"

# ── 1. Health check ──────────────────────────────────────────────────────────
header "1. Health check"
assert_http "GET /health" "$SERVICE_URL/health"

# ── 2. Crear ticket (CLI) ────────────────────────────────────────────────────
header "2. Crear ticket ZNRX desde CLI"
output=$($CLI create "tarea de prueba automatizada desde test-dev.sh, prioridad media" 2>&1)
echo "$output"
assert_ok "CLI create — respuesta contiene 'Ticket creado'" "$output" "Ticket creado"

CREATED_KEY=$(echo "$output" | grep -oE 'ZNRX-[0-9]+' | head -1)
if [ -z "$CREATED_KEY" ]; then
    red "No se pudo extraer el key del ticket creado"
    FAIL=$((FAIL+1))
else
    green "Key extraído: $CREATED_KEY"
fi

# ── 3. Summarize (CLI) ───────────────────────────────────────────────────────
header "3. Summarize ticket $CREATED_KEY"
if [ -n "$CREATED_KEY" ]; then
    output=$($CLI summarize "$CREATED_KEY" 2>&1)
    echo "$output"
    assert_ok "CLI summarize — respuesta contiene el key" "$output" "$CREATED_KEY"
else
    red "Skipped (no key disponible)"
    FAIL=$((FAIL+1))
fi

# ── 4. Update ticket (CLI) ───────────────────────────────────────────────────
header "4. Actualizar ticket $CREATED_KEY"
if [ -n "$CREATED_KEY" ]; then
    output=$($CLI update "$CREATED_KEY" "cambiar prioridad a alta y agregar comentario: actualizado por test-dev.sh" 2>&1)
    echo "$output"
    assert_ok "CLI update — respuesta contiene el key" "$output" "$CREATED_KEY"
else
    red "Skipped (no key disponible)"
    FAIL=$((FAIL+1))
fi

# ── 5. Search (CLI) ──────────────────────────────────────────────────────────
header "5. Búsqueda NL → JQL"
output=$($CLI list-issues "tareas abiertas de esta semana" 2>&1)
echo "$output"
assert_ok "CLI list — devuelve resultados" "$output" "resultado"

# ── 6. Directo via HTTP (Service Layer) ─────────────────────────────────────
header "6. POST /issues/search directo"
assert_http "POST /issues/search" \
    "$SERVICE_URL/issues/search" POST \
    '{"query": "tareas abiertas prioridad alta"}'

# ── 7. GET /issues/{key}/summary directo ────────────────────────────────────
header "7. GET /issues/{key}/summary directo"
if [ -n "$CREATED_KEY" ]; then
    assert_http "GET /issues/$CREATED_KEY/summary" "$SERVICE_URL/issues/$CREATED_KEY/summary"
else
    red "Skipped (no key disponible)"
    FAIL=$((FAIL+1))
fi

# ── 8. Validación de seguridad: input vacío ──────────────────────────────────
header "8. Seguridad: input vacío debe devolver 422"
code=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "$SERVICE_URL/issues" \
    -H "Content-Type: application/json" \
    -d '{"text": ""}')
if [ "$code" = "422" ]; then
    green "Input vacío rechazado con 422"
    PASS=$((PASS+1))
else
    red "Input vacío debería devolver 422, obtuvo $code"
    FAIL=$((FAIL+1))
fi

# ── Resumen ──────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════"
echo "  Resultado: $PASS passed / $FAIL failed"
if [ -n "$CREATED_KEY" ]; then
    echo "  Ticket creado: https://jira.zurich.com/browse/$CREATED_KEY"
fi
echo "══════════════════════════════════════"

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
