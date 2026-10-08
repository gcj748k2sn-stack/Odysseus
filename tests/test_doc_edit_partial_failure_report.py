"""A turn whose last edit failed after an earlier edit landed is not "unchanged".

notes/resolvedissues.md, *"Closing summary under-reports / stays silent"* (the
owed check, session d16f7a83, 2026-07-29): four ``edit_document`` calls - v2
written, one rejected, v3 written, one rejected - and the turn closed with
*"I couldn't apply the edit - the document is unchanged ... rejected 1
attempt"*. The success is dropped when a later edit fails, and the failure
notice assumed nothing had landed.

Drives the real ``stream_agent_loop`` with scripted rounds.
"""

import asyncio
import json
from types import SimpleNamespace

from src.turn_report import doc_edit_failed_notice

_EDIT = "```edit_document\n<<<FIND>>>\na\n<<<REPLACE>>>\nb\n<<<END>>>\n```"
_REJECTED = "No edits applied — none of the FIND blocks matched the document content (skipped 1)"


def _run(monkeypatch, results):
    import src.agent_loop as agent_loop

    monkeypatch.setattr(agent_loop, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(agent_loop, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(agent_loop, "estimate_tokens", lambda *a, **k: 10)
    # The user's own document: the approval gate stays open (user_content_trust).
    monkeypatch.setattr(agent_loop, "document_is_user_trusted", lambda doc: True)
    monkeypatch.setattr(agent_loop, "record_ai_document_write", lambda *a, **k: None)
    # A document tool's own result re-arms the gate; the recorded turn predates
    # the gate, and the report logic under test does not depend on it.
    import src.tool_capabilities as tool_capabilities
    for module in (agent_loop, tool_capabilities):
        monkeypatch.setattr(module, "tool_result_should_arm_gate", lambda *a, **k: False)
    replies = [_EDIT] * len(results) + [""]

    async def fake_stream(*args, **kwargs):
        reply = replies.pop(0) if replies else ""
        if reply:
            yield "data: " + json.dumps({"delta": reply}) + "\n\n"
        yield "data: [DONE]\n\n"

    pending = list(results)

    async def execute(block, *args, **kwargs):
        return ("edit_document", pending.pop(0))

    monkeypatch.setattr(agent_loop, "stream_llm_with_fallback", fake_stream)
    monkeypatch.setattr(agent_loop, "execute_tool_block", execute)
    doc = SimpleNamespace(id="doc-7", title="Guide", language="markdown",
                          current_content="a", version_count=1)

    async def collect():
        return [c async for c in agent_loop.stream_agent_loop(
            "http://local.test/v1", "small-local-model",
            [{"role": "user", "content": "edit the document"}],
            active_document=doc, session_id="s-partial", owner="alice",
            max_rounds=len(results) + 1, relevant_tools={"edit_document"},
        )]

    text = ""
    for chunk in asyncio.run(collect()):
        if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
            try:
                ev = json.loads(chunk[6:])
            except json.JSONDecodeError:
                continue
            if isinstance(ev.get("delta"), str):
                text += ev["delta"]
    return text


def _landed(version):
    return {"output": f'Document edited: "Guide" (v{version}, 1 edit(s))', "doc_id": "doc-7",
            "title": "Guide", "language": "markdown", "content": "b", "version": version,
            "action": "edit", "applied": 1}


def test_recorded_shape_names_the_version_that_landed(monkeypatch):
    text = _run(monkeypatch, [_landed(2), {"error": _REJECTED}, _landed(3), {"error": _REJECTED}])
    assert "unchanged" not in text.lower()
    assert "v3" in text and "Guide" in text
    assert "missing" in text


def test_all_edits_failed_still_says_unchanged(monkeypatch):
    """Negative control: nothing landed, so the original notice is right."""
    text = _run(monkeypatch, [{"error": _REJECTED}, {"error": _REJECTED}])
    assert "document is unchanged" in text.lower()


def test_last_edit_landed_has_no_failure_notice(monkeypatch):
    text = _run(monkeypatch, [{"error": _REJECTED}, _landed(2)])
    assert "unchanged" not in text.lower()
    assert "missing" not in text


def test_notice_wording():
    assert "unchanged" in doc_edit_failed_notice(1, "r").lower()
    partial = doc_edit_failed_notice(2, "r", {"title": "Guide", "version": 3})
    assert "v3" in partial and "2 attempts were rejected" in partial
    assert "unchanged" not in partial.lower()
    assert "1 attempt was rejected" in doc_edit_failed_notice(1, "r", {"title": "G", "version": 2})
    # An approval placeholder or a write without a version is not a landed edit.
    assert "unchanged" in doc_edit_failed_notice(1, "r", {"title": "G", "version": None}).lower()
