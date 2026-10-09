"""Tool selection for local endpoints: keywords and topic detection only.

Local servers (llama.cpp, LM Studio) reuse their prompt cache only for an
unchanged prefix, and the chat template renders the tool list at the top of
the prompt. Similarity search picks a different, partly random set for
similar messages (a greeting got `ui_control` once and not the next time), so
every new chat re-reads the whole prompt. Keyword selection is deterministic:
the same kind of message gets the same tools, and a new chat can reuse the
previous chat's cached prompt start (notes: "Similarity search adds random
tools …"). An offline replay of 263 agent turns found keywords + topic
detection offered the needed tools as often as similarity search.

This reuses upstream's keyword logic (`ToolIndex.get_tools_for_query`) with
retrieval stubbed out, and adds tool names written in the message. MCP tools are not keyword-selected, so on local endpoints they are
offered only through their own paths (intent domains, explicit requests).
Set ODYSSEUS_LOCAL_TOOL_SIMILARITY=1 to restore similarity search.

`ui_control` (the largest schema, ~4,300 chars) is kept only for messages that
name a UI action (mode, incognito, model switch, a panel or view, an explicit
"turn on/off the research/search/shell"). Not "research on X" / "search on
X", which are ordinary requests, and not themes (maintainer, 2026-10-09). Upstream's keyword lists and topic detection add it for
generic words ("enable", "disable", "turn on", "open", "show", "settings"),
so "disable the alarm" carried it and changed the tool list for that message.
"""
from __future__ import annotations

import os
import re
from typing import Iterable, Optional, Set

from src.tool_index import ALWAYS_AVAILABLE, ToolIndex

_TOOL_NAME_RE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")

_UI_PANELS = r"(?:chats|documents|email|gallery|inbox|library|memories|memory|notes|sessions|settings|skills)"
_UI_TOGGLES = r"(?:research|search|web search|shell|incognito)"
UI_ACTION_RE = re.compile(
    r"\b(?:"
    r"(?:agent|chat|plan) mode|set mode|incognito"
    r"|(?:switch|change) (?:the )?model"
    rf"|(?:open|show|close|hide) (?:the |my )?(?:\w+ )?(?:panel|sidebar)"
    rf"|(?:open|show) (?:the |my )?{_UI_PANELS}"
    rf"|(?:turn|switch) (?:on|off) (?:the )?{_UI_TOGGLES}"
    r"|ui_control"
    r")\b",
    re.IGNORECASE,
)


def keyword_only(endpoint_url: Optional[str]) -> bool:
    """True for local endpoints unless similarity search is switched back on."""
    if os.environ.get("ODYSSEUS_LOCAL_TOOL_SIMILARITY", "").strip().lower() in {"1", "true", "yes", "on"}:
        return False
    if not endpoint_url:
        return False
    try:
        from src.model_context import is_local_endpoint
        return bool(is_local_endpoint(endpoint_url))
    except Exception:
        return False


def _keyword_index() -> ToolIndex:
    index = ToolIndex.__new__(ToolIndex)     # no embedding model, no ChromaDB
    index.retrieve = lambda query, k=8: []
    return index


def select(query: str, known_tool_names: Iterable[str]) -> Set[str]:
    """The tools for `query`: always-available + upstream's keyword hints +
    tool names the message mentions. Deterministic."""
    query = str(query or "")
    tools = _keyword_index().get_tools_for_query(query, always_include=set(ALWAYS_AVAILABLE))
    ql = query.lower()
    known = set(known_tool_names)
    tools.update(name for name in _TOOL_NAME_RE.findall(ql) if name in known)
    return tools


def narrow_ui_control(tools: Set[str], message: str) -> Set[str]:
    """Drop ui_control unless the message names a UI action."""
    if "ui_control" in tools and not UI_ACTION_RE.search(str(message or "")):
        tools = set(tools)
        tools.discard("ui_control")
    return tools
