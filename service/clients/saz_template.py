"""
Renders the SAZ deployment description from structured PR data.
No Claude call — all fields come from the workflow result.
"""

import os

_TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "templates", "saz", "despliegue.template.md"
)

_ENV_LABELS = {
    "developer": "DEVELOPER",
    "test":      "TEST",
    "uat":       "UAT",
    "prod":      "PROD",
    "master":    "PROD",
    "main":      "PROD",
}


def _env_label(target: str) -> str:
    return _ENV_LABELS.get(target.lower(), target.upper())


def render_deployment_saz(
    *,
    issue_key: str | None,
    repo: str,
    target: str,
    branch: str,
    base_branch: str,
    pr_id: int | str,
    pr_url: str,
    project_label: str = "OV",
) -> tuple[str, str]:
    """
    Return (summary, description) for a SAZ deployment ticket.
    Reads the template from templates/saz/despliegue.template.md.
    Falls back to an inline template if the file is missing.
    """
    env = _env_label(target)
    task_label = issue_key if issue_key else repo
    pr_link_label = f"Pull Request {pr_id}" + (f": {issue_key}" if issue_key else "")

    summary_parts = [f"Despliegue ambiente {env}", project_label, repo]
    if issue_key:
        summary_parts.append(issue_key)
    summary = " - ".join(summary_parts)

    try:
        with open(_TEMPLATE_PATH, encoding="utf-8") as f:
            tpl = f.read()
        description = (
            tpl
            .replace("{ENV}", env)
            .replace("{proyecto}", project_label)
            .replace("{repositorio}", repo)
            .replace("{task}", task_label)
            .replace("pr_id", str(pr_id))
            .replace("{feature/fix}", branch)
            .replace("{destino}", base_branch)
            .replace("{link_pr_azure}", f"[{pr_link_label}]({pr_url})")
        )
    except FileNotFoundError:
        description = (
            f"Solicito su apoyo para realizar el despliegue en ambiente {env}:\n\n"
            f"Proyecto: {repo}\n"
            f"PR-1: {pr_id}\n"
            f"Origen: {branch}\n"
            f"Destino: {base_branch}\n"
            f"> [{pr_link_label}]({pr_url})"
        )

    return summary, description
