"""A short "decide, then act" rule for local models.

Small local reasoning models (Bonsai 2, Qwen 3.5 9B) spend minutes weighing
options nobody raised, or reasoning about a tool result that surprised them,
at ~10 tokens/s. The base rules already say not to second-guess a successful
tool; this adds the part they lack: commit to a choice, and take a surprising
result at face value.

Appended to the first system message for local endpoints only. The text is
fixed, so the prompt prefix stays stable for the server's cache.
"""
from __future__ import annotations

from typing import Dict, List

from src.sticky_tools import is_local_endpoint

DECISION_RULE = (
    "## Deciding\n"
    "- Decide, then act. When what you have is enough, choose the most "
    "reasonable option and make the call or give the answer; don't weigh "
    "alternatives nobody asked about.\n"
    "- If a tool result surprises you, trust it and say so in one line "
    "instead of reasoning about how it happened."
)


def apply(messages: List[Dict], endpoint_url: str) -> List[Dict]:
    """Return messages with the rule appended to the leading system message."""
    if not messages or not is_local_endpoint(endpoint_url):
        return messages
    first = messages[0]
    content = first.get("content") if isinstance(first, dict) else None
    if first.get("role") != "system" or not isinstance(content, str):
        return messages
    if DECISION_RULE in content:
        return messages
    return [{**first, "content": f"{content.rstrip()}\n\n{DECISION_RULE}"}, *messages[1:]]
