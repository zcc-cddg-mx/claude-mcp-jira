"""
Map commits to Jira issue keys.
Priority: 1) regex in commit message  2) regex in branch name  3) None (Claude fallback handled upstream)
"""

import re
from typing import Optional

_KEY_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")


def extract_issue_key(message: str, branch: Optional[str] = None) -> Optional[str]:
    """
    Return the first Jira issue key found in the commit message, then in the branch name.
    Returns None if no key is found.
    """
    m = _KEY_PATTERN.search(message)
    if m:
        return m.group(1)
    if branch:
        m = _KEY_PATTERN.search(branch)
        if m:
            return m.group(1)
    return None
