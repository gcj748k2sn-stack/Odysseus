"""A LAN address in the prompt must not delete the document tools, and must
not turn the request into machine work.

notes/todo.md, *"A LAN address in the prompt deletes every document tool"*.
*"create a document with temperature and humidity data from
http://192.168.0.185"* produced no document, three times (2026-07-29): the
named-machine alternative of ``_LOCAL_COMPUTER_REFERENCE_RE`` accepted
``on|from`` + ANY word (``from http``), and the Terminus branch of
``stream_agent_loop`` then *assigned* ``_WORKSPACE_TERMINUS_TOOLS`` over the
selection — discarding ``create_document``, which retrieval had ranked first
and the classifier had asked for (``domains=['documents', 'web']``). The model
used ``write_file`` on ``/tmp`` and reported success.

Fix (a): on the Terminus branch, keep every domain the user's words selected
(``_terminus_toolset``). Verified live 2026-10-04 23:09 — ``create_document``
was sent — but the same turn then spent eleven rounds in ``bash`` (ping, port
scans, listing ``~/Documents``), because the URL still counted as a machine.

Fix (b): only configured machines count — Cookbook servers and SSH aliases
(``src/named_machines.py``, unit tests in ``test_named_machines.py``). The
"this computer" phrasings are unchanged. Fix (c), the every-turn
``_local_computer_rules()`` injection, is still open.
"""
import asyncio
import json

import pytest

import src.agent_loop as al
import src.tool_index as tool_index

DOC_TOOLS = al._DOMAIN_TOOL_MAP["documents"]
AUTHORING_TOOLS = DOC_TOOLS - al._ADMIN_TOOLS  # manage_documents rides in with _ADMIN_TOOLS
TERMINUS = al._WORKSPACE_TERMINUS_TOOLS
LAN_PROMPT = "create a document with temperature and humidity data from http://192.168.0.185"
MACHINES = frozenset({"mediaserver", "gpu-box"})
NONE = frozenset()

# Reaches the classifier with domains={'files'} (the item named "list files on
# mediaserver", but `\bfile\b` misses "files", so that prompt has no domains).
NAMED_MACHINE_PROMPT = "list the folder /srv on mediaserver"
# A configured machine AND document words: the Terminus branch with fix (a).
MACHINE_DOC_PROMPT = "write a document with the disk usage on mediaserver"


def _intent(text):
    return al._classify_agent_request([{"role": "user", "content": text}], text)


# ── fix (b): which prompts count as machine-targeted ──

@pytest.mark.parametrize("text", [
    LAN_PROMPT,
    "create a document about mushroom growth from wikipedia",
    "write a report on climate change",
])
def test_document_requests_are_not_machine_requests(text):
    assert "documents" in _intent(text)["domains"]
    assert not al._looks_like_local_computer_request(text, NONE)
    # …and naming machines that exist elsewhere does not change that.
    assert not al._looks_like_local_computer_request(text, MACHINES)


@pytest.mark.parametrize("text", [
    "fact check the document and correct it",
    "create a new document about pink oyster mushroom",
])
def test_plain_document_requests_do_not(text):
    assert not al._looks_like_local_computer_request(text, MACHINES)


@pytest.mark.parametrize("text", [
    NAMED_MACHINE_PROMPT,
    "download qwen3 on the gpu box",
    MACHINE_DOC_PROMPT,
])
def test_configured_machines_still_count(text):
    assert al._looks_like_local_computer_request(text, MACHINES)
    assert not al._looks_like_local_computer_request(text, NONE)


@pytest.mark.parametrize("text", [
    "check the disk usage on this computer",
    "read my local files",
    "what is running on my machine",
])
def test_this_computer_needs_no_configuration(text):
    assert al._looks_like_local_computer_request(text, NONE)


def test_default_reads_the_configured_names(monkeypatch):
    monkeypatch.setattr(al, "configured_machine_names", lambda: MACHINES)
    assert al._looks_like_local_computer_request(NAMED_MACHINE_PROMPT)
    monkeypatch.setattr(al, "configured_machine_names", lambda: NONE)
    assert not al._looks_like_local_computer_request(NAMED_MACHINE_PROMPT)


def test_unreadable_configuration_means_no_named_machines(monkeypatch):
    def _boom():
        raise RuntimeError("settings unreadable")
    monkeypatch.setattr(al, "configured_machine_names", _boom)
    assert not al._looks_like_local_computer_request(NAMED_MACHINE_PROMPT)
    assert al._looks_like_local_computer_request("read my local files")


# ── fix (a): the helper ──

@pytest.mark.parametrize("text", [
    LAN_PROMPT,
    "create a document about mushroom growth from wikipedia",
    MACHINE_DOC_PROMPT,
])
def test_terminus_toolset_keeps_the_document_tools(text):
    tools = al._terminus_toolset(_intent(text)["domains"])
    assert DOC_TOOLS <= tools
    assert TERMINUS <= tools


def test_named_machine_files_request_gets_exactly_terminus():
    domains = _intent(NAMED_MACHINE_PROMPT)["domains"]
    assert domains == {"files"}, "prompt no longer exercises the union"
    assert al._terminus_toolset(domains) == set(TERMINUS)


def test_named_machine_cookbook_request_keeps_cookbook_tools():
    """_local_computer_rules() tells the model to use Cookbook tools for a
    named machine; the clobber used to remove them."""
    tools = al._terminus_toolset(_intent("download qwen3 on mediaserver")["domains"])
    assert {"download_model", "list_cookbook_servers"} <= tools
    assert tools.isdisjoint(DOC_TOOLS)


def test_unknown_domain_names_are_ignored():
    assert al._terminus_toolset(["no-such-domain"]) == set(TERMINUS)
    assert al._terminus_toolset(None) == set(TERMINUS)


# ── end to end through stream_agent_loop ──

class _FakeIndex:
    """Retrieval as recorded for the LAN prompt: create_document ranked first,
    plus noise (manage_calendar) that nothing asked for."""

    def index_mcp_tools(self, *a, **k):
        return None

    def get_tools_for_query(self, query, k=8, always_include=None):
        return set(tool_index.ALWAYS_AVAILABLE) | {"create_document", "web_fetch", "manage_calendar"}


def _schema_names(schemas):
    return {(s.get("function") or {}).get("name") or s.get("name") for s in (schemas or [])}


def _turn(monkeypatch, message, machines):
    """Run one round; return (tool names sent, whether the Terminus branch ran)."""
    sent = {"tools": None}
    terminus_calls = []

    async def _fake_stream(_candidates, messages, **kw):
        if sent["tools"] is None:
            sent["tools"] = kw.get("tools")
        yield "data: " + json.dumps({"delta": "ok"}) + "\n\n"
        yield "data: [DONE]\n\n"

    real_terminus_toolset = al._terminus_toolset

    def _recording_terminus_toolset(domains):
        terminus_calls.append(domains)
        return real_terminus_toolset(domains)

    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "blocked_tools_for_owner", lambda owner: set(), raising=False)
    monkeypatch.setattr(al, "_load_mcp_disabled_map", lambda: {}, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)
    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)
    monkeypatch.setattr(al, "configured_machine_names", lambda: machines)
    monkeypatch.setattr(al, "_terminus_toolset", _recording_terminus_toolset)
    monkeypatch.setattr(tool_index, "get_tool_index", lambda: _FakeIndex())

    async def _run():
        return [c async for c in al.stream_agent_loop(
            "https://api.openai.com/v1", "gpt-test",
            [{"role": "user", "content": message}],
            max_rounds=1,
        )]

    asyncio.run(_run())
    return _schema_names(sent["tools"]), bool(terminus_calls)


def test_lan_prompt_is_a_document_turn_not_a_machine_turn(monkeypatch):
    """The live failure of 2026-10-04 23:09: with the URL no longer a
    machine, the model gets the document tools and no shell."""
    names, terminus = _turn(monkeypatch, LAN_PROMPT, NONE)
    assert not terminus
    assert "create_document" in names
    assert "web_fetch" in names
    assert "bash" not in names


def test_machine_turn_with_document_words_keeps_document_tools(monkeypatch):
    """Fix (a), still needed when the machine is real."""
    names, terminus = _turn(monkeypatch, MACHINE_DOC_PROMPT, MACHINES)
    assert terminus, "Terminus branch did not run — the test would be vacuous"
    assert "bash" in names
    assert "create_document" in names
    assert "manage_calendar" not in names  # retrieval noise is still dropped


def test_named_machine_turn_sends_no_document_tools(monkeypatch):
    names, terminus = _turn(monkeypatch, NAMED_MACHINE_PROMPT, MACHINES)
    assert terminus
    assert "bash" in names
    assert names.isdisjoint(AUTHORING_TOOLS)


def test_unconfigured_name_is_not_a_machine_turn(monkeypatch):
    _, terminus = _turn(monkeypatch, NAMED_MACHINE_PROMPT, NONE)
    assert not terminus
