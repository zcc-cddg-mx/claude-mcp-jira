import os

import httpx
import typer
from dotenv import load_dotenv

load_dotenv()

app = typer.Typer()

SERVICE_URL = os.environ.get("SERVICE_URL", "http://localhost:8000")
USER = os.environ.get("JIRA_CLI_USER", "anonymous")


@app.command()
def create(text: str = typer.Argument(..., help="Descripción del ticket en lenguaje natural")):
    """Crea un ticket Jira a partir de texto libre."""
    typer.echo(f"Procesando: {text}")

    try:
        response = httpx.post(
            f"{SERVICE_URL}/issues",
            json={"text": text},
            headers={"x-user": USER},
            timeout=30,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        typer.echo(f"Error del servicio: {e.response.text}", err=True)
        raise typer.Exit(code=1)
    except httpx.ConnectError:
        typer.echo(f"No se pudo conectar al service layer en {SERVICE_URL}", err=True)
        raise typer.Exit(code=1)

    data = response.json()
    typer.echo(f"  Tipo: {data['issueType']} | Prioridad: {data['priority']}")
    typer.echo(f"  Resumen: {data['summary']}")
    typer.echo(f"Ticket creado: {data['key']}")


if __name__ == "__main__":
    app()
