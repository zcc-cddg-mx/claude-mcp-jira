# Servicios systemd — Ecosistema Developer Automation

**Fecha:** 2026-08-25  
**Estado:** Producción local (WSL2)

---

## Visión general

Todos los agentes del ecosistema corren como servicios de usuario systemd.  
Arrancan automáticamente con WSL, se reinician solos si caen, y no requieren sesión activa (linger habilitado).

```
WSL arranca
    │
    └─► systemd --user
            ├─ claude-mcp-jira.service   :18000 (service) + :18001 (MCP)
            ├─ simple-jira-agent.service :8101
            └─ simple-pr-agent.service   :8102
```

---

## Inventario de servicios

| Servicio | Puerto(s) | Unit file | Wrapper | Estado |
|----------|-----------|-----------|---------|--------|
| `claude-mcp-jira` | `:18000` + `:18001` | `~/.config/systemd/user/claude-mcp-jira.service` | `scripts/start_service.sh` | ✅ Activo |
| `simple-jira-agent` | `:8101` | `~/.config/systemd/user/simple-jira-agent.service` | `start_service.sh` | ✅ Activo |
| `simple-pr-agent` | `:8102` | `~/.config/systemd/user/simple-pr-agent.service` | `start_service.sh` | ✅ Activo |

---

## Patrón de implementación

Cada servicio sigue el mismo patrón de tres archivos:

### 1. Unit file (`~/.config/systemd/user/<nombre>.service`)

```ini
[Unit]
Description=<nombre> — descripción
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/idavid/dev/claude/<repo>
ExecStart=/bin/bash /home/idavid/dev/claude/<repo>/scripts/start_service.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

- `Type=simple` — el wrapper es el proceso principal; systemd lo monitorea directamente.
- `Restart=on-failure` + `RestartSec=5` — reinicio automático con cooldown de 5s.
- El unit file **no se comitea** al repo — vive en `~/.config/systemd/user/`.

### 2. Wrapper script (`scripts/start_service.sh` — versionado en el repo)

Responsabilidades del wrapper:
1. Cargar `.env` desde la raíz del repo (`set -a; source .env; set +a`).
2. Aplicar overrides de entorno específicos de WSL (paths de certs, puertos, `APP_ENV`).
3. Resolver el entorno conda (reutilizando `_conda_env.sh` cuando aplica).
4. Liberar puertos si están ocupados (arranque limpio).
5. Arrancar el proceso uvicorn en background y guardar su PID.
6. Instalar trap `SIGTERM`/`SIGINT` para apagado limpio.
7. Usar `wait -n` para salir si cualquier proceso hijo muere → systemd reinicia todo.

**Ventaja de versionar el wrapper:** permite actualizar la lógica de arranque con un `git pull` sin tocar la configuración de systemd.

### 3. Linger (una sola vez por máquina)

```bash
loginctl enable-linger $USER
```

Permite que los servicios de usuario corran aunque no haya sesión activa. Persistente — no necesita repetirse tras reinicios.

---

## claude-mcp-jira — caso especial (dos procesos)

`claude-mcp-jira` arranca dos servicios en el mismo unit:

```
start_service.sh
    ├─ uvicorn service.main:app     → :18000  (service layer — FastAPI)
    └─ uvicorn jira_mcp.server:app  → :18001  (MCP server — SSE)
```

El wrapper usa `wait -n` para detectar si cualquiera de los dos muere y forzar el reinicio del stack completo:

```bash
wait -n "$SERVICE_PID" "$MCP_PID" 2>/dev/null || true
# Si uno muere, matar el otro y salir → systemd reinicia ambos
kill "$SERVICE_PID" "$MCP_PID" 2>/dev/null || true
wait "$SERVICE_PID" "$MCP_PID" 2>/dev/null || true
```

---

## Comandos de gestión

```bash
# Estado de todos los servicios del ecosistema
systemctl --user status claude-mcp-jira simple-jira-agent simple-pr-agent

# Reiniciar uno
systemctl --user restart claude-mcp-jira

# Logs en vivo
journalctl --user -u claude-mcp-jira -f

# Logs directos de uvicorn (más detallados que journal)
tail -f /tmp/mcp-jira-service.log
tail -f /tmp/mcp-jira-mcp.log

# Health check rápido (equivalente a developer-assistant health)
curl -s http://localhost:18000/health
curl -s http://localhost:18001/sse  # MCP — espera SSE, CTRL+C para salir
curl -s http://localhost:8101/health
curl -s http://localhost:8102/health
```

---

## Actualizar un servicio tras cambios de código

```bash
# 1. Hacer git pull / editar código
cd /home/idavid/dev/claude/claude-mcp-jira
git pull

# 2. Reiniciar el servicio (recarga código automáticamente)
systemctl --user restart claude-mcp-jira

# 3. Verificar
systemctl --user status claude-mcp-jira --no-pager
```

No es necesario tocar el unit file para actualizaciones de código — el wrapper y el código están en el repo.

---

## Reinstalar el unit file (solo si cambia la ruta del wrapper)

```bash
cp ~/.config/systemd/user/claude-mcp-jira.service /tmp/backup.service
# editar el unit file
systemctl --user daemon-reload
systemctl --user restart claude-mcp-jira
```

---

## Diagnóstico

```bash
# ¿Los puertos están ocupados?
ss -tlnp | grep -E '18000|18001|8101|8102'

# ¿El servicio está fallando en bucle?
systemctl --user status claude-mcp-jira
journalctl --user -u claude-mcp-jira --since "5 min ago"

# Forzar restart limpio
systemctl --user stop claude-mcp-jira
sleep 1
systemctl --user start claude-mcp-jira
```
