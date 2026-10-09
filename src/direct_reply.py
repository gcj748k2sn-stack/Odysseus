"""Token cap for the direct low-signal reply path.

Upstream caps that path at ``min(max_tokens or 128, 128)``: meant for a short
reply to "hi" or "thanks". The path also takes plain questions in a new chat
without a workspace ("In at most three sentences: what is the difference
between RAM and flash …"), and on a thinking model the reasoning counts
against ``max_tokens``, so 128 tokens ran out before any answer (notes: "A
plain question in a new chat without a workspace gets a 128-token reply cap").

Brevity is left to the model; the cap only bounds a runaway reply. A limit
set by the request or preset is used as given.
"""
from __future__ import annotations

from typing import Optional

DEFAULT_MAX_TOKENS = 4096


def max_tokens(requested: Optional[int]) -> int:
    try:
        value = int(requested or 0)
    except (TypeError, ValueError):
        value = 0
    return value if value > 0 else DEFAULT_MAX_TOKENS
