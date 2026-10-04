"""A LAN address in the prompt must not delete the document tools.

docs/todo.md, *"A LAN address in the prompt deletes every document tool"*.
*"create a document with temperature and humidity data from
http://192.168.0.185"* produced no document, three times (2026-07-29): the
named-machine alternative of ``_LOCAL_COMPUTER_REFERENCE_RE`` matches
``from http``, and the Terminus branch of ``stream_agent_loop`` then
*assigned* ``_WORKSPACE_TERMINUS_TOOLS`` over the selection — discarding
``create_document``, which retrieval had ranked first and the classifier had
asked for (``domains=['documents', 'web']``). The model used ``write_file``
on ``/tmp`` and reported success.

Fix (a) of the item: keep every domain the user's words selected on top of
the Terminus set (``_terminus_toolset``). The regex itself (fix b) and the
every-turn ``_local_computer_rules()`` injection (fix c) are unchanged here.
"""
import asyncio
import json

import pytest

import src.agent_loop as al
import src.tool_index as tool_index

DOC_TOOLS = al._DOMAIN_TOOL_MAP["documents"]
TERMINUS = al._WORKSPACE_TERMINUS_TOOLS
LAN_PROMPT = "create a document with temperature and humidity data from http://192.168.0.185"


def _intent(text):
    return al._classify_agent_request([{"role": "user", "content": text}], text)


# ── the trigger, pinned so a regex change is noticed here ──

@pytest.mark.parametrize("text", [
    LAN_PROMPT,
    "create a document about mushroom growth from wikipedia",
    "write a report on climate change",
])
def test_these_document_requests_take_the_terminus_branch(text):
    """Still true after the fix — this is fix (b)'s territory, recorded so the
    tests below are known to exercise the branch rather than skip it."""
    assert al._looks_like_local_computer_request(text)
    assert "documents" in _intent(text)["domains"]


@pytest.mark.parametrize("text", [
    "fact check the document and correct it",
    "create a new document about pink oyster mushroom",
])
def test_plain_document_requests_do_not(text):
    assert not al._looks_like_local_computer_request(text)


# ── the helper ──

@pytest.mark.parametrize("text", [
    LAN_PROMPT,
    "create a document about mushroom growth from wikipedia",
    "write a report on climate change",
])
def test_terminus_toolset_keeps_the_document_tools(text):
    tools = al._terminus_toolset(_intent(text)["domains"])
    assert DOC_TOOLS <= tools
    assert TERMINUS <= tools


# Negative control from the item. The item named "list files on mediaserver",
# but that prompt never reaches the Terminus branch on a fresh chat: the
# classifier's `\bfile\b` does not match "files", so it has no domains, is
# low-signal and goes out with no tools at all (pre-existing, recorded in
# docs/todo.md under item 27). This one reaches the branch with
# domains=['files'], so the union is exercised and must add nothing.
NAMED_MACHINE_PROMPT = "list the folder /srv on mediaserver"


def test_named_machine_files_request_gets_exactly_terminus():
    text = NAMED_MACHINE_PROMPT
    assert al._looks_like_local_computer_request(text)
    domains = _intent(text)["domains"]
    assert domains == {"files"}, "prompt no longer exercises the union"
    assert al._terminus_toolset(domains) == set(TERMINUS)


def test_named_machine_cookbook_request_keeps_cookbook_tools():
    """_local_computer_rules() tells the model to use Cookbook tools for a
    named machine; the clobber used to remove them."""
    text = "download qwen3 on mediaserver"
    tools = al._terminus_toolset(_intent(text)["domains"])
    assert {"download_model", "list_cookbook_servers"} <= tools
    assert tools.isdisjoint(DOC_TOOLS)


def test_unknown_domain_names_are_ignored():
    assert al._terminus_toolset(["no-such-domain"]) == set(TERMINUS)
    assert al._terminus_toolset(None) == set(TERMINUS)


# ── end to end through stream_agent_loop ──

class _FakeIndex:
    """Retrieval as recorded for the LAN prompt: create_document ranked first,
    plus noise that the Terminus branch is right to drop."""

    def index_mcp_tools(self, *a, **k):
        return None

    def get_tools_for_query(self, query, k=8, always_include=None):
        return set(tool_index.ALWAYS_AVAILABLE) | {"create_document", "web_fetch", "manage_calendar"}


def _schema_names(schemas):
    return {(s.get("function") or {}).get("name") or s.get("name") for s in (schemas or [])}


def _tools_sent(monkeypatch, message):
    sent = {"tools": None}

    async def _fake_stream(_candidates, messages, **kw):
        if sent["tools"] is None:
            sent["tools"] = kw.get("tools")
        yield "data: " + json.dumps({"delta": "ok"}) + "\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "blocked_tools_for_owner", lambda owner: set(), raising=False)
    monkeypatch.setattr(al, "_load_mcp_disabled_map", lambda: {}, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)
    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)
    monkeypatch.setattr(tool_index, "get_tool_index", lambda: _FakeIndex())

    async def _run():
        return [c async for c in al.stream_agent_loop(
            "https://api.openai.com/v1", "gpt-test",
            [{"role": "user", "content": message}],
            max_rounds=1,
        )]

    asyncio.run(_run())
    return _schema_names(sent["tools"])


def test_lan_prompt_sends_create_document(monkeypatch):
    names = _tools_sent(monkeypatch, LAN_PROMPT)
    assert "bash" in names, "Terminus branch did not run — the test would be vacuous"
    assert "create_document" in names
    assert "manage_calendar" not in names  # retrieval noise is still dropped


def test_named_machine_turn_sends_no_document_tools(monkeypatch):
    names = _tools_sent(monkeypatch, NAMED_MACHINE_PROMPT)
    assert "bash" in names
    # manage_documents (list/read/tidy) arrives with _ADMIN_TOOLS on every
    # admin turn, before and after the fix; the authoring tools must not.
    assert names.isdisjoint(DOC_TOOLS - al._ADMIN_TOOLS)
