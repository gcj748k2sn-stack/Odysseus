"""A tool that stopped at an approval card did not run, so nothing may report it.

notes/todo.md, *"A document edit waiting on an approval card is reported as
done"*. The approval placeholder result (``approval_required: True``) has no
``error`` key, so the document-report gate counted it as a successful edit and
the turn closed with *"Updated the document."* while the document was unchanged.
The non-document closing report had the same gap (``Ran `write_file` — Waiting
for an exact user approval.``).

The approved continuation is the other half: once the user allows the action,
it runs at the start of the next turn and that turn reports it.

Drives the real ``stream_agent_loop`` with the gate armed by untrusted context,
as ``test_external_context_tool_gate.py`` does.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest

from src.turn_report import (
    _side_effect_tool_summary,
    doc_tool_result_landed,
)

_PLACEHOLDER = {
    "output": "Waiting for an exact user approval.",
    "exit_code": None,
    "approval_required": True,
    "ask_user": {"kind": "tool_approval", "approval_id": "x"},
}


def _deltas(generator):
    async def _collect():
        return [chunk async for chunk in generator]

    events = []
    for chunk in asyncio.run(_collect()):
        if not chunk.startswith("data: ") or chunk.startswith("data: [DONE]"):
            continue
        try:
            events.append(json.loads(chunk[6:]))
        except json.JSONDecodeError:
            pass
    text = "".join(e["delta"] for e in events if isinstance(e.get("delta"), str))
    return events, text


def _patch(monkeypatch, agent_loop, reply, execute):
    monkeypatch.setattr(
        agent_loop, "get_setting", lambda key, default=None: default, raising=False,
    )
    monkeypatch.setattr(agent_loop, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(agent_loop, "estimate_tokens", lambda *a, **k: 10)

    async def fake_stream(*args, **kwargs):
        yield "data: " + json.dumps({"delta": reply}) + "\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(agent_loop, "stream_llm_with_fallback", fake_stream)
    monkeypatch.setattr(agent_loop, "execute_tool_block", execute)


def _document():
    return SimpleNamespace(
        id="document-7", title="Draft", language="markdown",
        current_content="original", version_count=4,
    )


def _tainted_edit_turn(monkeypatch):
    """One round: the model sends update_document; the gate raises a card."""
    from src.prompt_security import untrusted_context_message
    import src.agent_loop as agent_loop

    async def should_not_execute(*args, **kwargs):
        raise AssertionError("unapproved document edit reached executor")

    _patch(
        monkeypatch, agent_loop,
        "```update_document\nreplacement\n```", should_not_execute,
    )
    events, text = _deltas(
        agent_loop.stream_agent_loop(
            "http://local.test/v1",
            "small-local-model",
            [
                {"role": "user", "content": "update this document"},
                untrusted_context_message("stored context", "untrusted"),
            ],
            active_document=_document(),
            session_id="pending-report-session",
            owner="alice",
            max_rounds=1,
            relevant_tools={"update_document"},
        )
    )
    approval = next(
        e["ask_user"] for e in events
        if (e.get("ask_user") or {}).get("kind") == "tool_approval"
    )
    agent_loop.tool_approval_store.consume(
        approval["approval_id"], decision="deny",
        owner="alice", session_id="pending-report-session",
    )
    return text


# ── The recorded failure ──────────────────────────────────────────────────────

def test_document_edit_waiting_on_a_card_is_not_reported_as_done(monkeypatch):
    text = _tainted_edit_turn(monkeypatch)
    assert "Allow this task to continue?" in text
    assert "Updated" not in text


def test_the_previous_gate_reproduces_the_false_report(monkeypatch):
    """Mutation: restore the old condition and the false line comes back.

    Without this, the test above could pass because the loop never reached the
    report at all.
    """
    import src.agent_loop as agent_loop

    monkeypatch.setattr(
        agent_loop, "doc_tool_result_landed", lambda r: not r.get("error"),
    )
    text = _tainted_edit_turn(monkeypatch)
    assert "Updated" in text


# ── The approved continuation reports the edit ────────────────────────────────

def test_approved_document_edit_is_reported_when_it_runs(monkeypatch):
    from src.tool_approvals import ToolApprovalStore, document_content_digest
    from src.tool_capabilities import capabilities_for_action
    import src.agent_loop as agent_loop

    store = ToolApprovalStore()
    pending = store.create(
        owner="alice", session_id="s-1", origin_run_id="run-1",
        tool_name="update_document", content="replacement", workspace=None,
        document_id="document-7", document_version=4,
        document_digest=document_content_digest("original"),
        external_untrusted_context_seen=True,
        capabilities=capabilities_for_action("update_document", "replacement"),
    )
    grant = store.consume(
        pending.approval_id, decision="approve", owner="alice", session_id="s-1",
    )
    ran = []

    async def execute(block, *args, **kwargs):
        ran.append(block.tool_type)
        return ("update_document", {
            "doc_id": "document-7", "title": "Draft", "language": "markdown",
            "content": "replacement", "version": 5,
        })

    _patch(monkeypatch, agent_loop, "", execute)  # the model says nothing
    _, text = _deltas(
        agent_loop.stream_agent_loop(
            "http://local.test/v1", "small-local-model",
            [{"role": "user", "content": "update this document"}],
            active_document=_document(), session_id="s-1", owner="alice",
            max_rounds=1, exact_approval=grant,
        )
    )
    assert ran == ["update_document"]
    assert "Draft" in text and "v5" in text


def test_failed_approved_edit_is_not_reported_as_done(monkeypatch):
    from src.tool_approvals import ToolApprovalStore, document_content_digest
    from src.tool_capabilities import capabilities_for_action
    import src.agent_loop as agent_loop

    store = ToolApprovalStore()
    pending = store.create(
        owner="alice", session_id="s-2", origin_run_id="run-1",
        tool_name="update_document", content="replacement", workspace=None,
        document_id="document-7", document_version=4,
        document_digest=document_content_digest("original"),
        external_untrusted_context_seen=True,
        capabilities=capabilities_for_action("update_document", "replacement"),
    )
    grant = store.consume(
        pending.approval_id, decision="approve", owner="alice", session_id="s-2",
    )

    async def execute(block, *args, **kwargs):
        return ("update_document", {"error": "Document changed since approval"})

    _patch(monkeypatch, agent_loop, "", execute)
    _, text = _deltas(
        agent_loop.stream_agent_loop(
            "http://local.test/v1", "small-local-model",
            [{"role": "user", "content": "update this document"}],
            active_document=_document(), session_id="s-2", owner="alice",
            max_rounds=1, exact_approval=grant,
        )
    )
    assert "Updated" not in text


# ── The predicate and the non-document report ─────────────────────────────────

@pytest.mark.parametrize("result, landed", [
    ({"doc_id": "d", "version": 2, "content": "x"}, True),
    ({"doc_id": "d", "version": 2, "exit_code": None}, True),
    (_PLACEHOLDER, False),
    ({"error": "FIND text not found", "exit_code": 1}, False),
    ({"error": "blocked", "exit_code": 1, "blocked": True}, False),
    (None, False),
])
def test_doc_tool_result_landed(result, landed):
    assert doc_tool_result_landed(result) is landed


def test_side_effect_report_skips_a_write_waiting_on_a_card():
    event = {
        "tool": "write_file", "desc": "write_file: APPROVAL REQUIRED",
        "output": _PLACEHOLDER["output"], "exit_code": None,
        "ask_user": _PLACEHOLDER["ask_user"],
    }
    assert _side_effect_tool_summary([event]) == ""


def test_side_effect_report_still_reports_a_write_that_ran():
    """Negative control for the skip: an ordinary write is still reported."""
    event = {"tool": "write_file", "output": "Wrote 12 bytes to a.txt", "exit_code": 0}
    assert _side_effect_tool_summary([event]) == "Wrote 12 bytes to a.txt"


def test_side_effect_report_skips_only_approval_cards():
    """An event carrying some other card kind is not treated as unexecuted."""
    event = {
        "tool": "write_file", "output": "Wrote 3 bytes to b.txt", "exit_code": 0,
        "ask_user": {"kind": "question"},
    }
    assert _side_effect_tool_summary([event]) == "Wrote 3 bytes to b.txt"
