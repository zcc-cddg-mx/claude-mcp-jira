import json
import os
from pathlib import Path

from anthropic import Anthropic

from .sanitizer import sanitize
from ..schemas import JiraIssuePayload

_client = Anthropic()
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.txt").read_text()


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def parse_create_issue(user_input: str) -> JiraIssuePayload:
    safe_input = sanitize(user_input)
    prompt = _load_prompt("create_issue").format(user_input=safe_input)

    message = _client.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = _strip_fences(message.content[0].text)
    data = json.loads(raw)
    return JiraIssuePayload(**data)
