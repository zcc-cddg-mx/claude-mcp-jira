import os

import httpx
import typer
from dotenv import load_dotenv

load_dotenv()

app = typer.Typer()

SERVICE_URL = os.environ.get("SERVICE_URL", "http://localhost:8000")
USER = os.environ.get("JIRA_CLI_USER", "anonymous")
_HEADERS = {"x-user": USER}


def _handle_error(response: httpx.Response, action: str) -> None:
    typer.echo(f"Error en {action}: {response.text}", err=True)
    raise typer.Exit(code=1)


def _client() -> httpx.Client:
    return httpx.Client(base_url=SERVICE_URL, headers=_HEADERS, timeout=30)


@app.command()
def create(text: str = typer.Argument(..., help="Descripción del ticket en lenguaje natural")):
    """Crea un ticket Jira a partir de texto libre."""
    typer.echo(f"Procesando: {text}")
    with _client() as client:
        try:
            r = client.post("/issues", json={"text": text})
            r.raise_for_status()
        except httpx.HTTPStatusError:
            _handle_error(r, "create")
        except httpx.ConnectError:
            typer.echo(f"No se pudo conectar al service layer en {SERVICE_URL}", err=True)
            raise typer.Exit(code=1)

    data = r.json()
    typer.echo(f"  Tipo: {data['issueType']} | Prioridad: {data['priority']}")
    typer.echo(f"  Resumen: {data['summary']}")
    typer.echo(f"Ticket creado: {data['key']}")


@app.command()
def update(
    key: str = typer.Argument(..., help="Clave del ticket (ej. PROJ-123)"),
    text: str = typer.Argument(..., help="Cambios a aplicar en lenguaje natural"),
):
    """Actualiza un ticket Jira existente."""
    typer.echo(f"Actualizando {key}: {text}")
    with _client() as client:
        try:
            r = client.patch(f"/issues/{key}", json={"text": text})
            r.raise_for_status()
        except httpx.HTTPStatusError:
            _handle_error(r, "update")
        except httpx.ConnectError:
            typer.echo(f"No se pudo conectar al service layer en {SERVICE_URL}", err=True)
            raise typer.Exit(code=1)

    typer.echo(f"Ticket actualizado: {r.json()['key']}")


@app.command()
def summarize(key: str = typer.Argument(..., help="Clave del ticket (ej. PROJ-123)")):
    """Genera un resumen legible de un ticket Jira."""
    typer.echo(f"Resumiendo {key}...")
    with _client() as client:
        try:
            r = client.get(f"/issues/{key}/summary")
            r.raise_for_status()
        except httpx.HTTPStatusError:
            _handle_error(r, "summarize")
        except httpx.ConnectError:
            typer.echo(f"No se pudo conectar al service layer en {SERVICE_URL}", err=True)
            raise typer.Exit(code=1)

    data = r.json()
    typer.echo(f"\n{data['key']}:")
    typer.echo(data["summary"])


@app.command()
def list_issues(query: str = typer.Argument(..., help="Búsqueda en lenguaje natural")):
    """Busca tickets Jira usando lenguaje natural."""
    typer.echo(f"Buscando: {query}")
    with _client() as client:
        try:
            r = client.post("/issues/search", json={"query": query})
            r.raise_for_status()
        except httpx.HTTPStatusError:
            _handle_error(r, "list")
        except httpx.ConnectError:
            typer.echo(f"No se pudo conectar al service layer en {SERVICE_URL}", err=True)
            raise typer.Exit(code=1)

    data = r.json()
    typer.echo(f"\n{data['total']} resultado(s):\n")
    for issue in data["issues"]:
        assignee = f" → {issue['assignee']}" if issue.get("assignee") else ""
        typer.echo(f"  {issue['key']}  [{issue['priority']}] [{issue['status']}]{assignee}")
        typer.echo(f"    {issue['summary']}")


if __name__ == "__main__":
    app()
