"""Local endpoints select tools by keywords and topic detection, not similarity.

Similarity search gave the same greeting different tools in two chats
(`ui_control` once), so the tool list at the top of the prompt changed and the
local server re-read everything; with identical tools a new chat reused 3,613
of 3,854 prompt tokens (notes: "Similarity search adds random tools …").
"""
from pathlib import Path

import pytest

from src import local_tool_selection as L
from src.tool_index import ALWAYS_AVAILABLE, ToolIndex

NAMES = ["read_file", "web_fetch", "manage_notes", "manage_calendar", "list_emails"]


@pytest.mark.parametrize("url", ["http://localhost:8090/v1", "http://127.0.0.1:1234/v1"])
def test_local_endpoints_use_keyword_selection(url, monkeypatch):
    monkeypatch.delenv("ODYSSEUS_LOCAL_TOOL_SIMILARITY", raising=False)
    assert L.keyword_only(url)


@pytest.mark.parametrize("url", ["https://api.openai.com/v1", "https://openrouter.ai/api/v1", "", None])
def test_remote_or_missing_endpoints_keep_similarity_search(url, monkeypatch):
    monkeypatch.delenv("ODYSSEUS_LOCAL_TOOL_SIMILARITY", raising=False)
    assert not L.keyword_only(url)


def test_the_switch_restores_similarity_search(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_LOCAL_TOOL_SIMILARITY", "1")
    assert not L.keyword_only("http://localhost:8090/v1")


def test_a_greeting_gets_only_the_always_available_tools_every_time():
    first = L.select("hello", NAMES)
    assert first == set(ALWAYS_AVAILABLE)
    assert all(L.select("hello", NAMES) == first for _ in range(5))


def test_english_keywords_still_select_their_tools():
    assert "list_emails" in L.select("check my unread email", NAMES)
    assert "manage_calendar" in L.select("add a meeting tomorrow", NAMES)


def test_keywords_match_whole_words_only():
    # "prevent" contains "event", "denote" contains "note".
    tools = L.select("how do I prevent this? denote it", NAMES)
    assert "manage_calendar" not in tools and "manage_notes" not in tools


def test_a_tool_named_in_the_message_is_offered_if_it_exists():
    tools = L.select("use web_fetch on that page, not made_up_tool", NAMES)
    assert "web_fetch" in tools and "made_up_tool" not in tools


def test_wired_before_similarity_search_and_before_sticky_tools():
    # Wiring test (structure, by design): the keyword path must run before the
    # similarity block so that block sees a filled set and skips, and before
    # stabilize so sticky tools keep the keyword set.
    src = Path(L.__file__).with_name("agent_loop.py").read_text(encoding="utf-8")
    call = src.index("_local_tool_selection.keyword_only(endpoint_url)")
    rag = src.index("asyncio.to_thread(tool_idx.get_tools_for_query")
    sticky = src.index("_relevant_tools = stabilize_tool_set(")
    assert call < rag < sticky
    assert src.rindex("if not guide_only and not _relevant_tools", 0, rag) > call, \
        "the similarity block must be skipped once the keyword set is filled"


# ── end to end through stream_agent_loop (harness as in test_terminus_keeps_intent_domains.py) ──

import asyncio
import json

import src.agent_loop as al
import src.tool_index as tool_index


class _NoisyIndex:
    """Similarity search as seen live for "hello": adds ui_control."""

    def __init__(self):
        self.queries = []

    def index_mcp_tools(self, *a, **k):
        return None

    def get_tools_for_query(self, query, k=8, always_include=None):
        self.queries.append(query)
        return set(ALWAYS_AVAILABLE) | {"ui_control", "todowrite"}


def _sent_tools(monkeypatch, url, message="Give me three ideas for my garden project"):
    sent = {"tools": None}

    async def _fake_stream(_candidates, messages, **kw):
        if sent["tools"] is None:
            sent["tools"] = kw.get("tools")
        yield "data: " + json.dumps({"delta": "ok"}) + "\n\n"
        yield "data: [DONE]\n\n"

    index = _NoisyIndex()
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "blocked_tools_for_owner", lambda owner: set(), raising=False)
    monkeypatch.setattr(al, "_load_mcp_disabled_map", lambda: {}, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)
    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)
    monkeypatch.setattr(tool_index, "get_tool_index", lambda: index)
    # Native tool calling, as live for Bonsai on llama.cpp; the harness's
    # unknown model would otherwise get no tool schemas at all.
    monkeypatch.setattr(al, "_agent_route_tool_mode", lambda *a, **k: (True, False, False))

    async def _run():
        return [c async for c in al.stream_agent_loop(
            url, "bonsai2-27b",
            # An earlier exchange: a first low-signal message is answered
            # directly, without tool selection.
            [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "Hello!"},
             {"role": "user", "content": message}],
            max_rounds=1)]

    asyncio.run(_run())
    names = {(s.get("function") or {}).get("name") or s.get("name") for s in (sent["tools"] or [])}
    return names, index.queries


def test_a_local_endpoint_never_asks_the_similarity_index(monkeypatch):
    monkeypatch.delenv("ODYSSEUS_LOCAL_TOOL_SIMILARITY", raising=False)
    first, queries = _sent_tools(monkeypatch, "http://localhost:8090/v1")
    assert queries == []
    assert first, "no tool schemas sent: the check below would pass for nothing"
    assert "ui_control" not in first
    again, _ = _sent_tools(monkeypatch, "http://localhost:8090/v1")
    assert again == first, "same message, same tools: the prompt start can be reused"


def test_the_switch_and_remote_endpoints_still_use_the_index(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_LOCAL_TOOL_SIMILARITY", "1")
    names, queries = _sent_tools(monkeypatch, "http://localhost:8090/v1")
    assert queries and "ui_control" in names
    monkeypatch.delenv("ODYSSEUS_LOCAL_TOOL_SIMILARITY")
    names, queries = _sent_tools(monkeypatch, "https://api.openai.com/v1")
    assert queries and "ui_control" in names


# ── ui_control only for a named UI action ──

@pytest.mark.parametrize("message", [
    "switch to agent mode", "open the notes panel", "show my settings", "turn on incognito",
    "change model to qwen", "turn off the research", "use ui_control to hide the sidebar",
])
def test_ui_actions_keep_ui_control(message):
    assert "ui_control" in L.narrow_ui_control({"ui_control", "ask_user"}, message)


@pytest.mark.parametrize("message", [
    "disable the alarm I set", "turn off the lights at 10", "enable logging in the config",
    "show me three ideas", "open the document and fix the typo", "change my voice",
    "do some research on oyster mushrooms", "search on the web for pink oyster fruiting",
    "switch to dark mode", "change the theme",
])
def test_generic_words_do_not(message):
    assert L.narrow_ui_control({"ui_control", "ask_user"}, message) == {"ask_user"}


def test_ui_control_follows_the_message_through_the_loop(monkeypatch):
    monkeypatch.delenv("ODYSSEUS_LOCAL_TOOL_SIMILARITY", raising=False)
    generic, _ = _sent_tools(monkeypatch, "http://localhost:8090/v1", "Please disable the alarm I set for tomorrow")
    ui, _ = _sent_tools(monkeypatch, "http://localhost:8090/v1", "Switch the app to agent mode")
    assert generic and "ui_control" not in generic
    assert "ui_control" in ui


def test_remote_endpoints_keep_upstreams_ui_control(monkeypatch):
    monkeypatch.delenv("ODYSSEUS_LOCAL_TOOL_SIMILARITY", raising=False)
    names, _ = _sent_tools(monkeypatch, "https://api.openai.com/v1", "Please disable the alarm I set for tomorrow")
    assert "ui_control" in names
