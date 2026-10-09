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
"""
from __future__ import annotations

import os
import re
from typing import Iterable, Optional, Set

from src.tool_index import ALWAYS_AVAILABLE, ToolIndex

_TOOL_NAME_RE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")


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
