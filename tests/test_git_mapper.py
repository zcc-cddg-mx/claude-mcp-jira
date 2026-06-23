from service.git.mapper import extract_issue_key


# ── Message matching ──────────────────────────────────────────────────────────

def test_key_in_message():
    assert extract_issue_key("fix: ZNRX-123 login bug") == "ZNRX-123"


def test_key_at_start_of_message():
    assert extract_issue_key("AIPROJECTS-42 implement search endpoint") == "AIPROJECTS-42"


def test_key_at_end_of_message():
    assert extract_issue_key("improve performance SCRX-7") == "SCRX-7"


def test_returns_first_key_when_multiple():
    assert extract_issue_key("ZNRX-1 refs ZNRX-2") == "ZNRX-1"


def test_key_with_multi_letter_project():
    assert extract_issue_key("AIPROJECTS-999 refactor") == "AIPROJECTS-999"


def test_no_key_in_message_no_branch():
    assert extract_issue_key("initial commit") is None


def test_no_key_in_message_branch_none():
    assert extract_issue_key("chore: update deps", None) is None


# ── Branch fallback ───────────────────────────────────────────────────────────

def test_falls_back_to_branch():
    assert extract_issue_key("small fix", "feature/ZNRX-55-auth") == "ZNRX-55"


def test_branch_key_ignored_when_message_has_key():
    result = extract_issue_key("fix ZNRX-10 bug", "feature/ZNRX-99-other")
    assert result == "ZNRX-10"


def test_no_key_in_message_or_branch():
    assert extract_issue_key("refactor utils", "main") is None


def test_branch_without_key():
    assert extract_issue_key("wip", "fix-login-flow") is None


# ── Pattern boundary ──────────────────────────────────────────────────────────

def test_lowercase_project_not_matched():
    assert extract_issue_key("znrx-123 fix") is None


def test_digits_only_project_not_matched():
    # "123-456" should not match — project must start with a letter
    assert extract_issue_key("123-456 fix") is None


def test_partial_uppercase_not_matched():
    # "Znrx-1" does not match — first char uppercase but rest not all uppercase/digit
    assert extract_issue_key("Znrx-1 fix") is None


def test_key_requires_at_least_two_chars_in_project():
    # The regex \b([A-Z][A-Z0-9]+-\d+)\b requires >=2 chars before the dash
    assert extract_issue_key("A-1 fix") is None
