import os
import json
import requests
import typer
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

app = typer.Typer()
client = Anthropic()

JIRA_URL = os.environ["JIRA_URL"].rstrip("/")
JIRA_PAT = os.environ["JIRA_PAT"]
JIRA_PROJECT_KEY = os.environ["JIRA_PROJECT_KEY"]
# Corporate firewall certificate — set REQUESTS_CA_BUNDLE in .env if needed
JIRA_CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE", True)

JIRA_HEADERS = {
    "Authorization": f"Bearer {JIRA_PAT}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

PROMPT_TEMPLATE = """You are a system that converts user requests into Jira issue JSON.
Given the following user input, return ONLY a valid JSON object with these fields:
- summary: short title (max 100 chars)
- description: detailed description in plain text
- priority: one of "Highest", "High", "Medium", "Low", "Lowest"
- issueType: one of "Bug", "Task", "Story", "Improvement"

User input: {user_input}

Return only the JSON object, no explanation."""


def parse_jira_payload(user_input: str) -> dict:
    message = client.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=512,
        messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(user_input=user_input)}],
    )
    raw = message.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def create_jira_issue(payload: dict) -> str:
    # Jira Server/Data Center uses REST API v2 with plain text description
    url = f"{JIRA_URL}/rest/api/2/issue"
    body = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": payload["summary"],
            "description": payload["description"],
            "issuetype": {"name": payload["issueType"]},
            "priority": {"name": payload["priority"]},
        }
    }
    response = requests.post(url, json=body, headers=JIRA_HEADERS, verify=JIRA_CA_BUNDLE)
    response.raise_for_status()
    return response.json()["key"]


@app.command()
def create(text: str = typer.Argument(..., help="Descripción del ticket en lenguaje natural")):
    """Crea un ticket Jira a partir de texto libre."""
    typer.echo(f"Procesando: {text}")

    try:
        payload = parse_jira_payload(text)
        typer.echo(f"  Tipo: {payload['issueType']} | Prioridad: {payload['priority']}")
        typer.echo(f"  Resumen: {payload['summary']}")
    except (json.JSONDecodeError, KeyError) as e:
        typer.echo(f"Error al interpretar la respuesta de Claude: {e}", err=True)
        raise typer.Exit(code=1)

    try:
        key = create_jira_issue(payload)
        typer.echo(f"Ticket creado: {key}")
    except requests.HTTPError as e:
        typer.echo(f"Error al crear el ticket en Jira: {e.response.text}", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
