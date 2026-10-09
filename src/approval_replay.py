"""What the model sees around a tool approval card.

When a tool call stops at an approval card, the loop streams the card's
question ("Allow this task to continue?") into the assistant reply so it
persists, and the call itself survives only in the reply's metadata. After
the user answers, the approved call runs and its result is injected as
untrusted context. The model then sees a question it never asked, followed by
the result of a call that is not in its view of the chat, and spends rounds
re-checking or reasoning about how the change happened (notes: "After an
approval the model does not know it made the call").

- ``context_view``: the model's view of a saved reply that stopped at a card.
  The card question is replaced by one line naming the call and the user's
  answer. The transcript the user sees is unchanged.
- ``result_text``: the injected result says it is the approved call's output.

Plain sentences, not a native tool call: a synthesized tool_call message would
need provider-specific fields (Gemini's thought_signature) that were never
returned for this call.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from src.tool_approval_scopes import (
    CHAT_SESSION_APPROVAL_DECISION,
    DENY_APPROVAL_DECISION,
    TASK_APPROVAL_DECISION,
)

_APPROVED = frozenset({TASK_APPROVAL_DECISION, CHAT_SESSION_APPROVAL_DECISION})
_ARG_CHARS = 80
_CALL_CHARS = 300


def _one_line(text: Any, limit: int) -> str:
    flat = " ".join(str(text if text is not None else "").split()).replace("`", "'")
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def describe_call(tool_name: str, content: Any) -> str:
    """`tool` (key: value; …) — a short, prose-shaped summary of the call."""
    args = ""
    try:
        parsed = json.loads(content) if isinstance(content, str) else content
    except (TypeError, ValueError):
        parsed = None
    if isinstance(parsed, dict) and parsed:
        args = "; ".join(f"{k}: {_one_line(v, _ARG_CHARS)}" for k, v in parsed.items())
    elif content:
        args = _one_line(content, _CALL_CHARS)
    args = _one_line(args, _CALL_CHARS)
    return f"`{tool_name}` ({args})" if args else f"`{tool_name}`"


def _outcome(resolved: Any) -> str:
    if resolved in _APPROVED:
        return "The user approved it."
    if resolved == DENY_APPROVAL_DECISION:
        return "The user denied it, so it did not run."
    return "It is waiting for the user's approval."


def _approval_cards(metadata: Optional[Dict[str, Any]]):
    events = (metadata or {}).get("tool_events") if isinstance(metadata, dict) else None
    for event in events if isinstance(events, list) else []:
        card = event.get("ask_user") if isinstance(event, dict) else None
        if isinstance(card, dict) and card.get("kind") == "tool_approval":
            yield event, card


def context_view(content: Any, metadata: Optional[Dict[str, Any]]) -> Any:
    """Replace approval-card questions in a saved reply with what was asked to run."""
    if not isinstance(content, str):
        return content
    lines = []
    text = content
    for event, card in _approval_cards(metadata):
        action = card.get("action") if isinstance(card.get("action"), dict) else {}
        tool = action.get("tool") or event.get("tool") or "a tool"
        question = str(card.get("question") or "").strip()
        if question and question in text:
            head, _, tail = text.rpartition(question)
            text = head + tail
        lines.append(
            f"(I asked to run {describe_call(tool, action.get('content'))}. "
            f"{_outcome(card.get('resolved'))})"
        )
    if not lines:
        return content
    text = text.strip()
    note = "\n".join(lines)
    return f"{text}\n\n{note}" if text else note


def result_text(tool_name: str, formatted_result: str) -> str:
    """Frame an approved call's output as the result of the model's own call."""
    return (
        f"The user approved your `{tool_name}` call and it has run. "
        f"This is its result:\n{formatted_result}"
    )
