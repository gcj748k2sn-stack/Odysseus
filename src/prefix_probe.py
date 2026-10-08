"""Report where a request's prompt stops matching the previous one in the same chat.

Local servers (llama.cpp, LM Studio) reuse the KV cache only for an unchanged
prefix, and hybrid models such as Qwen 3.5 / Bonsai 2 only up to a checkpoint
at a message boundary. Round 1 of a new message almost never hits the cache
(notes: "Round 1 of every turn re-prefills the whole prompt", "A different
tool set per message defeats prompt caching on local servers"). This names the
first message that changed, so the cause can be fixed instead of guessed.

Report-only: one log line per request, no message text (roles, lengths and
metadata labels only), never alters the request.
"""
from __future__ import annotations

import hashlib
import json
import logging
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

_MAX_SESSIONS = 64
_last: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()


def _digest(message: Any) -> str:
    try:
        raw = json.dumps(message, sort_keys=True, default=str, ensure_ascii=False)
    except Exception:
        raw = repr(message)
    return hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()[:12]


def _label(message: Any) -> str:
    if not isinstance(message, dict):
        return type(message).__name__
    meta = message.get("metadata") if isinstance(message.get("metadata"), dict) else {}
    source = meta.get("source") or meta.get("kind") or ""
    content = message.get("content")
    size = len(content) if isinstance(content, str) else len(json.dumps(content, default=str))
    extra = []
    if message.get("reasoning_content") or message.get("_turn_reasoning"):
        extra.append("reasoning")
    if message.get("tool_calls"):
        extra.append("tool_calls")
    tail = f" [{','.join(extra)}]" if extra else ""
    return f"{message.get('role', '?')}{':' + str(source)[:40] if source else ''} {size}ch{tail}"


def compare(session_id: Optional[str], round_num: int, messages: Sequence[Any],
            tool_names: Sequence[str]) -> Optional[Dict[str, Any]]:
    """Record this request and return how it differs from the previous one."""
    if not session_id:
        return None
    digests: List[str] = [_digest(m) for m in messages]
    tools = list(tool_names or [])
    prev = _last.pop(session_id, None)
    _last[session_id] = {"digests": digests, "tools": tools}
    while len(_last) > _MAX_SESSIONS:
        _last.popitem(last=False)
    if prev is None:
        return None
    first_diff = next(
        (i for i, (a, b) in enumerate(zip(prev["digests"], digests)) if a != b),
        min(len(prev["digests"]), len(digests)),
    )
    return {
        "round": round_num,
        "tools_same": prev["tools"] == tools,
        "tools_added": sorted(set(tools) - set(prev["tools"]))[:8],
        "tools_removed": sorted(set(prev["tools"]) - set(tools))[:8],
        "first_diff": first_diff,
        "prev_len": len(prev["digests"]),
        "len": len(digests),
        # Past the end of the previous request: the old prompt is intact and
        # the server can reuse all of it.
        "changed": (f"(none, +{len(digests) - first_diff} appended)" if first_diff >= len(prev["digests"])
                    else _label(messages[first_diff]) if first_diff < len(messages)
                    else "(none, request shorter)"),
    }


def log_request(session_id: Optional[str], round_num: int, messages: Sequence[Any],
                tool_names: Sequence[str]) -> None:
    try:
        d = compare(session_id, round_num, messages, tool_names)
    except Exception as exc:  # never break a turn over a diagnostic
        logger.debug("prefix probe failed: %s", exc)
        return
    if d is None:
        return
    logger.info(
        "[prefix-probe] session=%s round=%s tools_same=%s added=%s removed=%s "
        "first_diff=%s/%s (prev %s) changed=%s",
        str(session_id)[:8], d["round"], d["tools_same"], d["tools_added"], d["tools_removed"],
        d["first_diff"], d["len"], d["prev_len"], d["changed"],
    )
