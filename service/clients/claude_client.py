import json
import os
from pathlib import Path

from anthropic import Anthropic

from .sanitizer import sanitize
from ..schemas import JiraIssuePayload, SearchQueryStruct, UpdateIssuePayload

_client = Anthropic()
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.txt").read_text()


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def _call(prompt: str, max_tokens: int = 512) -> str:
    message = _client.messages.create(
        model=_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def parse_create_issue(user_input: str) -> JiraIssuePayload:
    safe_input = sanitize(user_input)
    prompt = _load_prompt("create_issue").format(user_input=safe_input)
    raw = _strip_fences(_call(prompt))
    return JiraIssuePayload(**json.loads(raw))


def parse_update_issue(user_input: str) -> UpdateIssuePayload:
    safe_input = sanitize(user_input)
    prompt = _load_prompt("update_issue").format(user_input=safe_input)
    raw = _strip_fences(_call(prompt))
    return UpdateIssuePayload(**json.loads(raw))


def summarize_issue(issue_data: dict) -> str:
    safe_data = sanitize(json.dumps(issue_data, ensure_ascii=False))
    prompt = _load_prompt("summarize_issue").format(issue_data=safe_data)
    return _call(prompt, max_tokens=256).strip()


def parse_search_query(user_input: str) -> SearchQueryStruct:
    safe_input = sanitize(user_input)
    prompt = _load_prompt("search_issues").format(user_input=safe_input)
    raw = _strip_fences(_call(prompt))
    return SearchQueryStruct(**json.loads(raw))
