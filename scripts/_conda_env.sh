#!/usr/bin/env bash
# Sourceado por dev.sh, test-dev.sh y test-mcp.sh.
# Exporta CONDA_ENV, PYTHON y UVICORN resolviendo el env claude-mcp-jira
# sin depender de un path absoluto hardcodeado.

_ENV_NAME="claude-mcp-jira"

if [ -n "$CONDA_PREFIX" ] && [[ "$CONDA_PREFIX" == *"$_ENV_NAME"* ]]; then
    CONDA_ENV="$CONDA_PREFIX"
elif command -v conda &>/dev/null; then
    CONDA_ENV="$(conda info --base 2>/dev/null)/envs/$_ENV_NAME"
else
    for _base in "$HOME/miniconda3" "$HOME/anaconda3" "$HOME/mambaforge" "/opt/conda"; do
        if [ -d "$_base/envs/$_ENV_NAME" ]; then
            CONDA_ENV="$_base/envs/$_ENV_NAME"
            break
        fi
    done
fi

if [ -z "$CONDA_ENV" ] || [ ! -d "$CONDA_ENV" ]; then
    echo "[dev] ERROR: conda env '$_ENV_NAME' no encontrado. Actívalo con: conda activate $_ENV_NAME" >&2
    exit 1
fi

PYTHON="$CONDA_ENV/bin/python"
UVICORN="$CONDA_ENV/bin/uvicorn"
