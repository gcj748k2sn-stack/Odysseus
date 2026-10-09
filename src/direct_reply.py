"""Token cap for the direct low-signal reply path.

Upstream caps that path at ``min(max_tokens or 128, 128)``: meant for a short
reply to "hi" or "thanks". The path also takes plain questions in a new chat
without a workspace ("In at most three sentences: what is the difference
between RAM and flash …"), and on a thinking model the reasoning counts
against ``max_tokens``, so 128 tokens ran out before any answer (notes: "A
plain question in a new chat without a workspace gets a 128-token reply cap").

Brevity is left to the model; the cap only bounds a runaway reply. A limit
set by the request or preset is used as given.

The path also sent the question with no system prompt. On Qwen 3.5 9B that
meant 7,000–16,000 chars of thinking (75–195 s, often the whole cap); with
Odysseus's own system prompt (no tools) 285–1,500 chars and 10–20 s. One-line
"be brief" messages barely helped (notes: "Direct reply path: no system
prompt, long thinking"; `scripts/probe_direct_reply.py`). So real questions get
that prompt; greetings ("hi", "thanks") stay as upstream sends them.
"""
from __future__ import annotations

from typing import Dict, List, Optional

DEFAULT_MAX_TOKENS = 4096


def max_tokens(requested: Optional[int]) -> int:
    try:
        value = int(requested or 0)
    except (TypeError, ValueError):
        value = 0
    return value if value > 0 else DEFAULT_MAX_TOKENS


def messages(question: str, casual: bool, system_prompt: str) -> List[Dict[str, str]]:
    """The request for the direct path: system prompt + question, or the question alone for a greeting."""
    user = {"role": "user", "content": question}
    if casual or not system_prompt:
        return [user]
    return [{"role": "system", "content": system_prompt}, user]
