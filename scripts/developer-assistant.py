#!/usr/bin/env python3
"""developer-assistant — CLI para claude-mcp-jira API Gateway (:18000)

Uso:
    developer-assistant.py --init          Configuración inicial
    developer-assistant.py health          Estado de los 4 servicios
    developer-assistant.py saz             Crear SAZ de despliegue (interactivo)
    developer-assistant.py deploy          Workflow completo: PR + SAZ
    developer-assistant.py worklog         Registrar horas desde git
    developer-assistant.py ticket          Crear o buscar ticket Jira
    developer-assistant.py status [id]     Estado de un workflow
"""

import argparse
import json
import sys
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

CONFIG_PATH = Path.home() / ".developer-assistant" / "config.json"

DEFAULT_CONFIG = {
    "api_url": "http://localhost:18000",
    "api_key": "",
    "default_project": "ZNRX",
    "default_repo": "ov-arizona-backend-ecuador",
    "default_team": "Soporte Oficina Virtual",
    "default_assignee": "SEBASTIAN.MAYORGA",
}

SERVICES = {
    "claude-mcp-jira service": ("http://localhost:18000", "/health"),
    "claude-mcp-jira MCP    ": ("http://localhost:18001", "/health"),
    "simple-jira-agent      ": ("http://localhost:8101",  "/health"),
    "simple-pr-agent        ": ("http://localhost:8102",  "/health"),
}

# ── colores ────────────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"{GREEN}✓{RESET} {msg}")
def err(msg):  print(f"{RED}✗{RESET} {msg}")
def info(msg): print(f"{CYAN}→{RESET} {msg}")
def warn(msg): print(f"{YELLOW}!{RESET} {msg}")
def bold(msg): print(f"{BOLD}{msg}{RESET}")

# ── config ─────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


def cmd_init(_args, _cfg):
    bold("Configuración inicial — developer-assistant")
    print(f"Se guardará en: {CONFIG_PATH}\n")
    cfg = load_config()
    cfg["api_url"]          = prompt("API URL",           cfg.get("api_url", DEFAULT_CONFIG["api_url"]))
    cfg["api_key"]          = prompt("API Key (MCP_API_KEY)", cfg.get("api_key", ""))
    cfg["default_project"]  = prompt("Proyecto por defecto",  cfg.get("default_project", DEFAULT_CONFIG["default_project"]))
    cfg["default_repo"]     = prompt("Repo por defecto",      cfg.get("default_repo",    DEFAULT_CONFIG["default_repo"]))
    cfg["default_team"]     = prompt("Equipo por defecto",    cfg.get("default_team",    DEFAULT_CONFIG["default_team"]))
    cfg["default_assignee"] = prompt("Assignee SAZ (username Jira)", cfg.get("default_assignee", DEFAULT_CONFIG["default_assignee"]))
    save_config(cfg)
    ok(f"Config guardada en {CONFIG_PATH}")

# ── API client ─────────────────────────────────────────────────────────────────

def api(cfg: dict, method: str, path: str, body: dict | None = None) -> dict:
    url = cfg["api_url"].rstrip("/") + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if cfg.get("api_key"):
        headers["X-API-Key"] = cfg["api_key"]
    req = urllib_request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib_request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        body_text = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code} — {body_text}") from e
    except URLError as e:
        raise RuntimeError(f"No se puede conectar a {url} — {e.reason}") from e

# ── helpers ────────────────────────────────────────────────────────────────────

def prompt(label: str, default: str | int | None = None) -> str:
    if default is not None and str(default):
        value = input(f"  {label} [{default}]: ").strip()
        return value if value else str(default)
    value = input(f"  {label}: ").strip()
    if not value:
        raise ValueError(f"'{label}' es requerido")
    return value


def prompt_opt(label: str, default: str = "") -> str:
    value = input(f"  {label} (opcional) [{default}]: ").strip()
    return value if value else default

# ── comandos ───────────────────────────────────────────────────────────────────

def cmd_health(_args, _cfg):
    bold("Estado de servicios")
    all_ok = True
    for name, (base, path) in SERVICES.items():
        try:
            req = urllib_request.Request(base + path, method="GET")
            with urllib_request.urlopen(req, timeout=3):
                ok(f"{name}  {base}")
        except Exception:
            err(f"{name}  {base}  — inactivo")
            all_ok = False
    if not all_ok:
        print()
        warn("Arrancar con: bash run_local.sh")


def cmd_saz(_args, cfg):
    """Crea un SAZ de despliegue a partir de un PR ya existente."""
    bold("Crear SAZ de despliegue")
    print()
    repo         = prompt("Repositorio",   cfg.get("default_repo"))
    task         = prompt("Descripción de la tarea")
    target       = prompt("Ambiente destino", "test")
    branch       = prompt("Rama origen (feature/...)")
    base_branch  = prompt("Rama base (destino del PR)", target)
    pr_id        = prompt("PR ID (Azure DevOps)")
    pr_url       = prompt("URL del PR")
    project_label= prompt("Label de proyecto", "OV")
    znrx_key     = prompt_opt("Ticket ZNRX relacionado")

    body = {
        "task": task,
        "repo": repo,
        "target": target,
        "branch": branch,
        "base_branch": base_branch,
        "pr_id": int(pr_id),
        "pr_url": pr_url,
        "project_label": project_label,
    }
    if znrx_key:
        body["znrx_key"] = znrx_key

    print()
    info("Creando SAZ...")
    try:
        result = api(cfg, "POST", "/issues/saz/deployment", body)
        ok(f"SAZ creado: {result.get('saz_key', result)}")
        if znrx_key:
            ok(f"Vinculado a: {znrx_key}")
    except RuntimeError as e:
        err(str(e))
        sys.exit(1)


def cmd_deploy(_args, cfg):
    """Workflow completo: crea PR en Azure DevOps + SAZ de despliegue."""
    bold("Workflow completo — PR + SAZ")
    print()
    repo          = prompt("Repositorio",          cfg.get("default_repo"))
    branch        = prompt("Rama feature")
    target        = prompt("Ambiente destino",      "test")
    ticket        = prompt("Ticket (ZNRX-XXXX o ID requerimiento)")
    task          = prompt("Descripción de la tarea")
    project_label = prompt("Label de proyecto",    "OV")
    znrx_key      = prompt_opt("ZNRX para vincular SAZ (si diferente al ticket)")

    body = {
        "repo": repo,
        "branch": branch,
        "target": target,
        "ticket": ticket,
        "task": task,
        "project_label": project_label,
    }
    if znrx_key:
        body["znrx_key"] = znrx_key

    print()
    info("[1/2] Creando PR en Azure DevOps...")
    info("[2/2] Creando SAZ de despliegue...")
    try:
        result = api(cfg, "POST", "/deployments/saz-workflow", body)
        pr_id  = result.get("pr_id")
        pr_url = result.get("pr_url", "")
        saz    = result.get("saz_key")
        ok(f"PR #{pr_id} creado — {pr_url}")
        ok(f"SAZ creado: {saz}")
        if znrx_key or ticket.startswith("ZNRX"):
            ok(f"Vinculado a: {znrx_key or ticket}")
    except RuntimeError as e:
        err(str(e))
        sys.exit(1)


def cmd_worklog(args, cfg):
    """Escanea commits git y registra worklogs en Jira."""
    bold("Registrar horas desde git")
    print()
    repo_name  = prompt_opt("Alias de repo registrado (repo_name)", cfg.get("default_repo", ""))
    since_days = prompt("Días hacia atrás", 7)
    dry_run_s  = prompt("Solo previsualizar (dry_run) [S/n]", "S")
    dry_run    = dry_run_s.strip().lower() not in ("n", "no")

    body: dict = {"since_days": int(since_days), "dry_run": dry_run}
    if repo_name:
        body["repo_name"] = repo_name

    print()
    action = "Previsualizando" if dry_run else "Registrando"
    info(f"{action} worklogs (últimos {since_days} días)...")
    try:
        result = api(cfg, "POST", "/git/sync", body)
        sessions = result.get("sessions", [])
        if not sessions:
            warn("No se encontraron sesiones de trabajo en el período.")
            return
        total_h = sum(s.get("estimated_hours", 0) for s in sessions)
        print(f"\n  {'Ticket':<15} {'Horas':>6}  Descripción")
        print(f"  {'─'*15} {'─'*6}  {'─'*40}")
        for s in sessions:
            key   = s.get("issue_key") or "sin-ticket"
            hours = s.get("estimated_hours", 0)
            msgs  = s.get("messages", [])
            desc  = msgs[0][:50] if msgs else ""
            print(f"  {key:<15} {hours:>5.1f}h  {desc}")
        print(f"\n  {'TOTAL':<15} {total_h:>5.1f}h")
        if dry_run:
            print()
            warn("Modo previsualización — nada fue registrado en Jira.")
            warn("Ejecutar de nuevo con dry_run=N para registrar.")
        else:
            print()
            ok(f"{len(sessions)} sesiones registradas en Jira.")
    except RuntimeError as e:
        err(str(e))
        sys.exit(1)


def cmd_ticket(args, cfg):
    """Crear un ticket Jira o buscar tickets."""
    bold("Jira — crear o buscar ticket")
    print()
    action = prompt("Acción", "buscar").lower()

    if action in ("buscar", "b", "search"):
        query   = prompt("Búsqueda en lenguaje natural")
        project = prompt_opt("Proyecto (opcional)", cfg.get("default_project", ""))
        body: dict = {"query": query}
        if project:
            body["project"] = project
        info("Buscando...")
        try:
            result = api(cfg, "POST", "/issues/search", body)
            issues = result if isinstance(result, list) else result.get("issues", [])
            if not issues:
                warn("No se encontraron tickets.")
                return
            print(f"\n  {'Key':<14} {'Estado':<15} {'Título'}")
            print(f"  {'─'*14} {'─'*15} {'─'*45}")
            for i in issues[:20]:
                key    = i.get("key", "")
                status = i.get("status", "")
                summ   = i.get("summary", "")[:50]
                print(f"  {key:<14} {status:<15} {summ}")
        except RuntimeError as e:
            err(str(e))
            sys.exit(1)

    else:
        project = prompt("Proyecto",    cfg.get("default_project"))
        text    = prompt("Descripción del ticket (lenguaje natural)")
        body = {"project": project, "text": text}
        info("Creando ticket...")
        try:
            result = api(cfg, "POST", "/issues", body)
            key = result.get("key") or result.get("issue_key") or result
            ok(f"Ticket creado: {key}")
        except RuntimeError as e:
            err(str(e))
            sys.exit(1)


def cmd_status(args, cfg):
    """Consulta el estado de un workflow."""
    bold("Estado de workflow")
    execution_id = getattr(args, "id", None) or prompt("Execution ID")
    try:
        result = api(cfg, "GET", f"/workflows/{execution_id}")
        status = result.get("status", "?")
        steps  = result.get("steps", [])
        color  = GREEN if status == "completed" else RED if status == "error" else YELLOW
        print(f"\n  Estado: {color}{status}{RESET}")
        if steps:
            print()
            for step in steps:
                name    = step.get("name", "")
                s_stat  = step.get("status", "")
                detail  = step.get("detail") or ""
                icon    = "✓" if s_stat == "done" else "✗" if s_stat == "error" else "·"
                c       = GREEN if s_stat == "done" else RED if s_stat == "error" else YELLOW
                print(f"  {c}{icon}{RESET} {name:<35} {detail[:40]}")
        result_data = result.get("result")
        if result_data:
            print(f"\n  Resultado: {json.dumps(result_data, ensure_ascii=False)}")
    except RuntimeError as e:
        err(str(e))
        sys.exit(1)


# ── main ───────────────────────────────────────────────────────────────────────

COMMANDS = {
    "init":    cmd_init,
    "health":  cmd_health,
    "saz":     cmd_saz,
    "deploy":  cmd_deploy,
    "worklog": cmd_worklog,
    "ticket":  cmd_ticket,
    "status":  cmd_status,
}


def main():
    parser = argparse.ArgumentParser(
        prog="developer-assistant",
        description="CLI para claude-mcp-jira API Gateway",
    )
    parser.add_argument(
        "command",
        choices=list(COMMANDS),
        help="Comando a ejecutar",
    )
    parser.add_argument(
        "id",
        nargs="?",
        help="ID de workflow (solo para 'status')",
    )
    args = parser.parse_args()

    cfg = load_config()
    if not cfg.get("api_key") and args.command not in ("init", "health"):
        warn(f"Sin API key — ejecuta: python developer-assistant.py --init")
        warn(f"O configura en {CONFIG_PATH}")
        print()

    try:
        COMMANDS[args.command](args, cfg)
    except KeyboardInterrupt:
        print("\nCancelado.")
        sys.exit(0)
    except ValueError as e:
        err(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
