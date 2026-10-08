"""Keep a chat's retrieved tool set stable on local model servers.

Tool retrieval picks a slightly different set for every message. The tool list
sits at the start of the prompt (Qwen-family chat templates render it ahead of
the system message), and Odysseus's system prompt documents each offered tool,
so any change invalidates the whole cached prefix: llama.cpp / LM Studio
re-read the entire conversation before the first token. Measured 2026-10-08
with the prefix probe: a follow-up message changed 9 of ~11 tools and diverged
at message 0 (notes: "A different tool set per message defeats prompt caching
on local servers").

So for local endpoints the retrieval result is unioned with what earlier
messages in the same chat retrieved. Only the retrieval step is affected:
domain seeding, the browser gate, document/email/upload rules, forced tools and
disabled_tools all still apply afterwards. A union that would exceed
MAX_TOOLS resets to the current set, so the prompt cannot grow without bound.
"""
from __future__ import annotations

import ipaddress
import logging
from collections import OrderedDict
from typing import Optional, Set
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

MAX_TOOLS = 24
_MAX_CHATS = 128
_sets: "OrderedDict[tuple, Set[str]]" = OrderedDict()


def is_local_endpoint(url: str) -> bool:
    """A model server on this machine or the LAN (where prompt caching is ours)."""
    try:
        host = (urlparse(url or "").hostname or "").lower()
    except Exception:
        return False
    if host in ("localhost", "host.docker.internal") or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


def stabilize(session_id: Optional[str], endpoint_url: str, model: str,
              tools: Optional[Set[str]], follow_up: bool = False) -> Optional[Set[str]]:
    """Return the tool set to use for this message (possibly widened).

    ``follow_up``: a low-signal message in an existing chat ("and times 4?").
    Retrieval on such text returns near-random tools (calendar, notes,
    endpoints - live 2026-10-08), so the union would grow on every message and
    never repeat. A follow-up reuses the chat's previous set exactly.
    """
    if not tools or not session_id or not is_local_endpoint(endpoint_url):
        return tools
    key = (str(session_id), str(model or ""))
    prev = _sets.pop(key, set())
    if follow_up and prev:
        _sets[key] = set(prev)
        logger.info("[sticky-tools] session=%s follow-up: reusing the previous %d tools", key[0][:8], len(prev))
        return set(prev)
    union = set(prev) | set(tools)
    if len(union) > MAX_TOOLS:
        union = set(tools)
        logger.info("[sticky-tools] session=%s reset: union would exceed %d tools", key[0][:8], MAX_TOOLS)
    elif prev and union != set(tools):
        logger.info("[sticky-tools] session=%s kept %d earlier tool(s): %s",
                    key[0][:8], len(union - set(tools)), sorted(union - set(tools))[:10])
    _sets[key] = set(union)
    while len(_sets) > _MAX_CHATS:
        _sets.popitem(last=False)
    return union
