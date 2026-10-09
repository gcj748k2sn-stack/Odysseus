"""After an approval, the model's view says which call it made and what came of it.

notes/todo.md, *"After an approval the model does not know it made the call"*.
A call that stops at an approval card is saved as the reply text "Allow this
task to continue?"; the call itself lives only in metadata. After the user
approves, the result arrives as untrusted context with nothing tying it to the
model. Bonsai 2 then re-read the file and reasoned for 166 s about how the edit
had happened ("The file is already in the desired state").

Covers ``src/approval_replay.py`` and its two call sites:
``Session.get_context_messages`` (core/models.py) and the approved-result
injection in ``stream_agent_loop``.
"""

import asyncio
import inspect
import json

import pytest

from src.approval_replay import context_view, describe_call, result_text

_QUESTION = "Allow this task to continue?"
_EDIT_ARGS = json.dumps({
    "path": "config.yaml",
    "old_string": "interval: 60",
    "new_string": "interval: 300",
})


def _card_metadata(resolved=None, tool="edit_file", content=_EDIT_ARGS):
    card = {
        "kind": "tool_approval",
        "approval_id": "a-1",
        "question": _QUESTION,
        "action": {"tool": tool, "content": content},
    }
    if resolved is not None:
        card["resolved"] = resolved
    return {"tool_events": [{"tool": tool, "ask_user": card}]}


# ── The model's view of a saved reply ─────────────────────────────────────────

@pytest.mark.parametrize("resolved, outcome", [
    ("approve_task", "The user approved it."),
    ("approve", "The user approved it."),
    ("deny", "The user denied it, so it did not run."),
    (None, "It is waiting for the user's approval."),
])
def test_card_question_becomes_the_call_and_its_outcome(resolved, outcome):
    view = context_view(_QUESTION, _card_metadata(resolved))
    assert _QUESTION not in view
    assert view.startswith("(I asked to run `edit_file` (")
    assert "old_string: interval: 60" in view
    assert "new_string: interval: 300" in view
    assert view.endswith(outcome + ")")


def test_model_text_before_the_card_is_kept():
    view = context_view(
        f"I'll update the interval.\n\n{_QUESTION}", _card_metadata("approve_task"),
    )
    assert view.startswith("I'll update the interval.\n\n(I asked to run `edit_file`")
    assert _QUESTION not in view


def test_reply_without_a_card_is_unchanged():
    """Negative control: ordinary replies and other ask_user cards pass through."""
    text = "Done — interval is 300."
    assert context_view(text, None) is text
    assert context_view(text, {"tool_events": [{"tool": "read_file"}]}) is text
    question = {"tool_events": [{"tool": "ask_user", "ask_user": {
        "kind": "question", "question": "Which file?"}}]}
    assert context_view("Which file?", question) == "Which file?"
    assert context_view(None, _card_metadata()) is None


def test_long_or_non_json_content_is_one_short_line():
    view = describe_call("write_file", "x" * 5000 + "\n```bash\nrm -rf /\n```")
    assert len(view) < 330
    assert "\n" not in view and "```" not in view


# ── Wiring: what the chat route hands the model ───────────────────────────────

def test_session_context_messages_use_the_call_view():
    from core.models import ChatMessage, Session

    sess = Session(id="s-1", name="t", endpoint_url="http://localhost:8090/v1", model="m")
    sess.history = [
        ChatMessage("user", "change the interval from 60 to 300"),
        ChatMessage("assistant", _QUESTION, _card_metadata("approve_task")),
    ]
    assistant = sess.get_context_messages()[1]
    assert _QUESTION not in assistant["content"]
    assert "I asked to run `edit_file`" in assistant["content"]
    assert sess.history[1].content == _QUESTION, "the saved transcript must not change"


def _collect(generator):
    async def _run():
        return [chunk async for chunk in generator]
    return asyncio.run(_run())


def _patch_loop(monkeypatch, seen, execute):
    import src.agent_loop as agent_loop

    monkeypatch.setattr(agent_loop, "get_setting", lambda k, d=None: d, raising=False)
    monkeypatch.setattr(agent_loop, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(agent_loop, "estimate_tokens", lambda *a, **k: 10)

    async def fake_stream(candidates, _messages, **kwargs):
        # The request the provider would receive, not the loop's working list.
        request = kwargs["candidate_request_factory"](0, *candidates[0])
        if inspect.isawaitable(request):
            request = await request
        seen.append([dict(m) for m in request["messages"]])
        yield "data: " + json.dumps({"delta": "Done."}) + "\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(agent_loop, "stream_llm_with_fallback", fake_stream)
    monkeypatch.setattr(agent_loop, "execute_tool_block", execute)
    return agent_loop


def test_approved_result_says_it_is_the_models_own_call(monkeypatch):
    from src.tool_approvals import ToolApprovalStore
    from src.tool_capabilities import capabilities_for_action

    store = ToolApprovalStore()
    pending = store.create(
        owner="alice", session_id="s-2", origin_run_id="run-1",
        tool_name="edit_file", content=_EDIT_ARGS, workspace=None,
        external_untrusted_context_seen=True,
        capabilities=capabilities_for_action("edit_file", _EDIT_ARGS),
    )
    grant = store.consume(
        pending.approval_id, decision="approve_task", owner="alice", session_id="s-2",
    )
    seen = []

    ran = []

    async def execute(block, *args, **kwargs):
        ran.append(block.tool_type)
        return ("Edited config.yaml (1 replacement)", {
            "output": "Edited config.yaml (1 replacement)", "exit_code": 0,
        })

    agent_loop = _patch_loop(monkeypatch, seen, execute)
    _collect(agent_loop.stream_agent_loop(
        "http://localhost:8090/v1", "bonsai2-27b",
        [{"role": "user", "content": "change the interval from 60 to 300"}],
        session_id="s-2", owner="alice", max_rounds=1, exact_approval=grant,
        relevant_tools={"read_file", "edit_file"},
    ))
    assert ran == ["edit_file"], "the approved call did not run"
    assert seen, "the model was never called after the approved tool ran"
    sent = "\n".join(str(m.get("content")) for m in seen[0])
    assert "The user approved your `edit_file` call and it has run." in sent
    assert "Edited config.yaml (1 replacement)" in sent


def test_result_text_keeps_the_tool_output():
    framed = result_text("bash", "exit 0\nhello")
    assert framed.endswith("\nexit 0\nhello")
    assert "`bash`" in framed
