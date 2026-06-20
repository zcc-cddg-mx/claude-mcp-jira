import json
import os
from pathlib import Path

from anthropic import Anthropic

from .sanitizer import sanitize
from ..schemas import AddCommentPayload, AssignIssuePayload, CloneIssuePayload, JiraIssuePayload, LabelsPayload, LinkIssuePayload, LogWorkPayload, SearchQueryStruct, SetPriorityPayload, TransitionPayload, UpdateIssuePayload

_client = Anthropic()
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

_LANG_INSTRUCTION = {
    "es": "Genera el resumen y la descripción del ticket en español.",
    "en": "Generate the ticket summary and description in English.",
}


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.txt").read_text()


def _lang_suffix() -> str:
    lang = os.environ.get("TICKET_LANG", "es").lower()
    return "\n" + _LANG_INSTRUCTION.get(lang, _LANG_INSTRUCTION["es"])


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


def _parse_json(raw: str, label: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}: invalid JSON from model ({exc.msg} at pos {exc.pos})") from exc


def parse_create_issue(user_input: str) -> JiraIssuePayload:
    safe_input = sanitize(user_input)
    prompt = _load_prompt("create_issue").format(user_input=safe_input) + _lang_suffix()
    raw = _strip_fences(_call(prompt))
    return JiraIssuePayload(**_parse_json(raw, "create_issue"))


def parse_update_issue(user_input: str) -> UpdateIssuePayload:
    safe_input = sanitize(user_input)
    prompt = _load_prompt("update_issue").format(user_input=safe_input) + _lang_suffix()
    raw = _strip_fences(_call(prompt))
    return UpdateIssuePayload(**_parse_json(raw, "update_issue"))


def summarize_issue(issue_data: dict) -> str:
    safe_data = sanitize(json.dumps(issue_data, ensure_ascii=False))
    prompt = _load_prompt("summarize_issue").format(issue_data=safe_data)
    return _call(prompt, max_tokens=256).strip()


def parse_transition_issue(user_input: str, available_transitions: list[dict]) -> TransitionPayload:
    safe_input = sanitize(user_input)
    transitions_str = json.dumps(available_transitions, ensure_ascii=False)
    prompt = _load_prompt("transition_issue").format(
        user_input=safe_input,
        available_transitions=transitions_str,
    )
    raw = _strip_fences(_call(prompt))
    return TransitionPayload(**_parse_json(raw, "transition_issue"))


def parse_log_work(user_input: str) -> LogWorkPayload:
    safe_input = sanitize(user_input)
    prompt = _load_prompt("log_work").format(user_input=safe_input)
    raw = _strip_fences(_call(prompt))
    return LogWorkPayload(**_parse_json(raw, "log_work"))


def parse_clone_issue(user_input: str, source: dict) -> CloneIssuePayload:
    if not user_input.strip():
        return CloneIssuePayload()
    safe_input = sanitize(user_input)
    f = source["fields"]
    prompt = _load_prompt("clone_issue").format(
        user_input=safe_input,
        original_summary=sanitize(f.get("summary", "")),
        original_description=sanitize(f.get("description", "") or ""),
    )
    raw = _strip_fences(_call(prompt))
    return CloneIssuePayload(**_parse_json(raw, "clone_issue"))


def parse_assign_issue(user_input: str) -> AssignIssuePayload:
    safe_input = sanitize(user_input)
    prompt = _load_prompt("assign_issue").format(user_input=safe_input)
    raw = _strip_fences(_call(prompt))
    return AssignIssuePayload(**_parse_json(raw, "assign_issue"))


def parse_set_priority(user_input: str) -> SetPriorityPayload:
    safe_input = sanitize(user_input)
    prompt = _load_prompt("set_priority").format(user_input=safe_input)
    raw = _strip_fences(_call(prompt))
    return SetPriorityPayload(**_parse_json(raw, "set_priority"))


def parse_add_comment(user_input: str) -> AddCommentPayload:
    safe_input = sanitize(user_input)
    prompt = _load_prompt("add_comment").format(user_input=safe_input)
    raw = _strip_fences(_call(prompt))
    return AddCommentPayload(**_parse_json(raw, "add_comment"))


def parse_link_issue(user_input: str, link_types: list[dict]) -> LinkIssuePayload:
    safe_input = sanitize(user_input)
    link_types_str = "\n".join(
        f'- "{t["name"]}" — outward: {t["outward"]} | inward: {t["inward"]}'
        for t in link_types
    )
    prompt = _load_prompt("link_issue").format(
        user_input=safe_input,
        link_types=link_types_str,
    )
    raw = _strip_fences(_call(prompt))
    return LinkIssuePayload(**_parse_json(raw, "link_issue"))


def parse_labels(user_input: str, current_labels: list[str]) -> LabelsPayload:
    safe_input = sanitize(user_input)
    prompt = _load_prompt("labels").format(
        user_input=safe_input,
        current_labels=json.dumps(current_labels, ensure_ascii=False),
    )
    raw = _strip_fences(_call(prompt))
    return LabelsPayload(**_parse_json(raw, "labels"))


def parse_search_query(user_input: str) -> SearchQueryStruct:
    safe_input = sanitize(user_input)
    prompt = _load_prompt("search_issues").format(user_input=safe_input)
    raw = _strip_fences(_call(prompt))
    return SearchQueryStruct(**_parse_json(raw, "search_issues"))
