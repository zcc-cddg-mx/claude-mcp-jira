"""
Renders the SAZ deployment description from structured PR data.
No Claude call — all fields come from the workflow result.
"""

import os

_TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "templates", "saz", "despliegue.template.md"
)

_ENV_LABELS = {
    "desarrollo": "DEVELOPER",
    "developer": "DEVELOPER",
    "test":      "TEST",
    "uat":       "UAT",
    "develop":   "PROD",
    "prod":      "PROD",
    "master":    "PROD",
    "main":      "PROD",
}

# Maps deployment target → base branch of the PR
# developer → developer branch (desarrollo)
# test      → test branch (pruebas)
# prod      → develop (DevOps promotes develop→main manually)
_TARGET_BASE_BRANCH = {
    "developer": "developer",
    "test":      "test",
    "prod":      "develop",
}


def get_base_branch_for_target(target: str) -> str:
    return _TARGET_BASE_BRANCH.get(target.lower(), target)


def _env_label(target: str) -> str:
    return _ENV_LABELS.get(target.lower(), target.upper())


def render_deployment_saz(
    *,
    task: str,
    repo: str,
    target: str,
    branch: str,
    base_branch: str,
    pr_id: int | str,
    pr_url: str,
    project_label: str = "OV",
    issue_key: str | None = None,
) -> tuple[str, str]:
    """
    Return (summary, description) for a SAZ deployment ticket.
    summary: Despliegue ambiente {ENV} - {project_label} - {task}
    description: rendered from templates/saz/despliegue.template.md
    """
    env = _env_label(target)
    pr_link_label = f"Pull Request {pr_id}" + (f": {issue_key}" if issue_key else "")

    summary = f"Despliegue ambiente {env} - {project_label} - {task}"

    try:
        with open(_TEMPLATE_PATH, encoding="utf-8") as f:
            tpl = f.read()
        description = (
            tpl
            .replace("{ENV}", env)
            .replace("{proyecto}", project_label)
            .replace("{repositorio}", repo)
            .replace("{task}", task)
            .replace("pr_id", str(pr_id))
            .replace("{feature/fix}", branch)
            .replace("{destino}", target)
            .replace("{link_pr_azure}", f"[{pr_link_label}]({pr_url})")
        )
    except FileNotFoundError:
        description = (
            f"Solicito su apoyo para realizar el despliegue en ambiente {env}:\n\n"
            f"Proyecto: {repo}\n"
            f"PR-1: {pr_id}\n"
            f"Origen: {branch}\n"
            f"Destino: {target}\n"
            f"> [{pr_link_label}]({pr_url})"
        )

    return summary, description
