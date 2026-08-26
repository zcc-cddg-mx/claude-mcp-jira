# Onboarding — developer-assistant

Guía de instalación y configuración del stack `claude-mcp-jira` como plataforma personal de automatización.

Al finalizar tendrás el comando `da` disponible desde cualquier directorio, con acceso a Jira, Azure DevOps y los flujos SAZ/Deploy.

---

## Paso 1 — Prerrequisitos

| Requisito | Verificar |
|-----------|-----------|
| `miniconda3` o `anaconda3` instalado | `conda --version` |
| Acceso a `jira.zurich.com` (red Zurich) | Navegar al sitio |
| PAT de Jira generado | Perfil → Personal Access Tokens |
| `TOKEN_AZURE` (Azure DevOps PAT) | Azure DevOps → User Settings → Personal Access Tokens |
| WSL2 con `systemd` habilitado | `cat /proc/1/comm` debe mostrar `systemd` |

Para habilitar systemd en WSL2 si no está activo, agregar a `/etc/wsl.conf`:

```ini
[boot]
systemd=true
```

Luego reiniciar WSL: `wsl --shutdown` desde PowerShell.

---

## Paso 2 — Clonar el repo y crear el entorno

```bash
# Clonar (ajustar ruta según preferencia)
git clone <url-repo> ~/dev/claude/claude-mcp-jira
cd ~/dev/claude/claude-mcp-jira

# Crear entorno conda
conda env create -f environment.yml
conda activate claude-mcp-jira
```

---

## Paso 3 — Configurar `.env`

```bash
cp .env.example .env
```

Editar `.env` y completar al menos estos valores:

```bash
# Jira
JIRA_URL=https://jira.zurich.com
JIRA_PAT=<tu-personal-access-token>
JIRA_DEFAULT_PROJECT=ZNRX       # proyecto por defecto

# Claude API (proxy interno Zurich)
ANTHROPIC_BASE_URL=https://genai-lounge-nx-litellm-uat-emea.zurich.com
ANTHROPIC_AUTH_TOKEN=<token-del-proxy>
ANTHROPIC_MODEL=eu.anthropic.claude-sonnet-4-6

# MCP
MCP_API_KEY=<clave-que-tú-elijas>

# Azure DevOps (para workflows PR + SAZ)
TOKEN_AZURE=<azure-devops-pat>
```

> **Certificados:** `jira.zurich.com` usa DigiCert — no requiere CA personalizado. Dejar `REQUESTS_CA_BUNDLE` vacío o comentado.

---

## Paso 4 — Arrancar el stack como servicio systemd

```bash
# Crear el unit file
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/claude-mcp-jira.service << 'EOF'
[Unit]
Description=claude-mcp-jira — service layer (:18000) + MCP server (:18001)
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/<tu-usuario>/dev/claude/claude-mcp-jira
ExecStart=/bin/bash /home/<tu-usuario>/dev/claude/claude-mcp-jira/scripts/start_service.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

# Reemplazar <tu-usuario> con el nombre real
sed -i "s/<tu-usuario>/$USER/g" ~/.config/systemd/user/claude-mcp-jira.service

# Habilitar y arrancar
systemctl --user daemon-reload
systemctl --user enable --now claude-mcp-jira

# Habilitar linger (el servicio corre aunque no haya sesión activa)
loginctl enable-linger $USER

# Verificar
systemctl --user status claude-mcp-jira --no-pager
```

El stack queda activo en `:18000` (service layer) y `:18001` (MCP server). Se reiniciará automáticamente con WSL.

---

## Paso 5 — Configurar `da` y verificar

**Alias permanente:**

```bash
echo '\n# developer-assistant\nalias da="python ~/dev/claude/claude-mcp-jira/scripts/developer-assistant.py"' >> ~/.zshrc
source ~/.zshrc
```

**Configuración inicial:**

```bash
da init
```

El comando pedirá interactivamente:

- API URL → `http://localhost:18000`
- API Key → el valor de `MCP_API_KEY` en `.env`
- Proyecto por defecto → `ZNRX`
- Repo por defecto → nombre de tu repo principal en Azure DevOps
- Equipo / Assignee SAZ → usuario Jira del responsable de despliegues (ej: `SEBASTIAN.MAYORGA`)
- Repos (uno a uno) → alias, ambiente destino por defecto, prefijo de rama, proyecto Jira

**Verificar el stack:**

```bash
da health
```

Salida esperada:

```
Estado de servicios
✓ claude-mcp-jira service  http://localhost:18000
✓ claude-mcp-jira MCP      http://localhost:18001
✓ simple-jira-agent        http://localhost:8101
✓ simple-pr-agent          http://localhost:8102
```

> Los puertos `:8101` y `:8102` son opcionales — si no tienes `simple-jira-agent` ni `simple-pr-agent` instalados, el health los marcará como inactivos pero los comandos principales (`saz`, `deploy`, `ticket`) funcionarán igual.

---

## Uso básico

```bash
da health           # estado de los 4 servicios
da repos            # repos configurados (marca el activo en verde)
da history          # últimas operaciones

da ticket           # crear o buscar ticket Jira
da worklog          # registrar horas desde git

da saz              # crear SAZ de despliegue (desde un PR existente)
da deploy           # workflow completo: PR Azure + SAZ en un paso

da status <id>      # estado de un workflow en ejecución
```

Desde dentro de un repo git reconocido, `saz` y `deploy` prerellenan repo, rama y ambiente automáticamente.

---

## Gestión del servicio

```bash
systemctl --user status claude-mcp-jira       # estado
systemctl --user restart claude-mcp-jira      # reiniciar (tras cambios de código)
systemctl --user stop claude-mcp-jira         # parar
journalctl --user -u claude-mcp-jira -f       # logs en vivo
```

Ver patrón completo en `arch/design/systemd-services.md`.
