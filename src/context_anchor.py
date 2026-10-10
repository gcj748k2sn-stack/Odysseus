"""Keep the turn's user message when a tool chain is trimmed to fit the context.

``trim_for_context`` drops the oldest conversation messages first and protects
only the last one, assuming it is the user's request. Inside an agent turn the
last message is a tool result and the request sits before all the tool rounds,
so a long tool chain (web research) can push it out. Chat templates of the
Qwen 3.5 family, Bonsai 2 included, then reject the request outright ("No user
query found in messages"), and any model loses the task it was working on.
"""
from __future__ import annotations

from typing import Dict, List, Optional


def latest_user(messages: List[Dict]) -> Optional[Dict]:
    """The newest user message: the request the current turn is answering."""
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "user":
            return message
    return None


def drop_oldest(messages: List[Dict], keep: Optional[Dict]) -> bool:
    """Remove the oldest message other than ``keep``, in place.

    Returns False when nothing but ``keep`` is left to drop, so a
    ``while too_big and drop_oldest(...)`` loop ends instead of spinning.
    """
    for index, message in enumerate(messages):
        if message is not keep:
            del messages[index]
            return True
    return False
