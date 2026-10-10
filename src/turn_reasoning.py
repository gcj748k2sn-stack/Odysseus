"""Send every tool round's thinking back to local servers, so the prompt prefix holds.

``_append_tool_results`` keeps ``reasoning_content`` on the newest assistant
message only. Qwen 3.5-family templates (Bonsai 2 too) render an in-turn
assistant message with its thinking when it is present, so a message is
rendered one way in the next request and another way in the one after. The
prompt then stops matching the server's cache inside the earlier rounds, and
llama.cpp / LM Studio re-read everything after that point on every round.

For local endpoints this restores each in-turn assistant message's thinking
from ``_turn_reasoning`` (which the loop never pops). Every message then
renders the same way in every later request. Thinking longer than
``MAX_CHARS`` is shortened the same way every time (head and tail), which
bounds the extra context without making the prefix unstable.

Earlier turns loaded from history carry no ``_turn_reasoning`` and are left
as they are. Remote endpoints are untouched.
"""
from __future__ import annotations

from typing import Dict, List

from src.sticky_tools import is_local_endpoint

MAX_CHARS = 4000
HEAD_CHARS = 1000
MARK = "\n[…]\n"


def shorten(reasoning: str) -> str:
    """Deterministic: the same input always gives the same output."""
    if len(reasoning) <= MAX_CHARS:
        return reasoning
    tail = MAX_CHARS - HEAD_CHARS - len(MARK)
    return reasoning[:HEAD_CHARS] + MARK + reasoning[-tail:]


def apply(messages: List[Dict], endpoint_url: str) -> List[Dict]:
    """Return messages whose in-turn assistant messages all carry their thinking."""
    if not messages or not is_local_endpoint(endpoint_url):
        return messages
    out: List[Dict] = []
    changed = False
    for message in messages:
        thinking = (
            message.get("_turn_reasoning")
            if isinstance(message, dict) and message.get("role") == "assistant"
            else None
        )
        if isinstance(thinking, str) and thinking.strip():
            want = shorten(thinking)
            if message.get("reasoning_content") != want:
                message = {**message, "reasoning_content": want}
                changed = True
        out.append(message)
    return out if changed else messages
