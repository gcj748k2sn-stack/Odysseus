"""Document-edit failure handling, driven through the real agent loop.

The unit tests for these fixes (`test_doc_edit_retry.py`,
`test_doc_report_gate_split.py`) call the helpers directly. These drive the
actual `stream_agent_loop` with a scripted LLM stream, so they cover the wiring
the unit tests can't see: that the retry directive really reaches the model's
next round, that the escalation counts across rounds, and that the end-of-turn
notice really replaces the "Done." a failed turn used to produce.

Why this matters more than usual here: **an organic run cannot test these
paths.** They only fire when the model emits a broken call shape, which after
the converter fix is rare — run 009660d2 (2026-07-19) edited cleanly on the
first attempt and never touched any of this code. Waiting for a real failure to
reappear is not a test strategy; injecting one is.

Harness follows the existing pattern in
`test_fenced_example_not_executed_for_native_models.py`: monkeypatch
`stream_llm_with_fallback`, keep the real loop body.
"""
import asyncio
import json

import src.agent_loop as al


def _collect(gen):
    async def _run():
        return [c async for c in gen]
    return asyncio.run(_run())


def _deltas(chunks):
    """Visible assistant text streamed to the user."""
    out = []
    for c in chunks:
        if c.startswith("data: ") and not c.startswith("data: [DONE]"):
            try:
                ev = json.loads(c[6:])
            except Exception:
                continue
            if isinstance(ev, dict) and "delta" in ev:
                out.append(ev["delta"])
    return "".join(out)


def _run_loop(monkeypatch, round_outputs, tool_results, max_rounds=4):
    """Drive the loop with scripted per-round model output and tool results.

    `round_outputs`: text the fake model emits each round.
    `tool_results`: dicts returned by execute_tool_block, in call order.
    Returns (chunks, prompts_seen) — prompts_seen is the message list handed to
    the model each round, which is how we verify the directive was fed back.
    """
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)
    # Merged 2026-10-06: upstream's untrusted-context gate treats any tool
    # result that carries text — an edit_document error included — as content
    # that arms it, after which a second document edit needs a sealed user
    # approval. These tests pin the end-of-turn report, not the gate (upstream
    # covers that in tests/test_external_context_tool_gate.py), so the gate is
    # held open here.
    from src.tool_capabilities import ToolGateDecision, ToolRunSecurityContext
    monkeypatch.setattr(
        ToolRunSecurityContext, "decision_for",
        lambda self, tool_name, content=None: ToolGateDecision(True),
    )

    results = list(tool_results)
    calls = []

    async def _fake_exec(block, *a, **k):
        calls.append(block)
        return ("edit_document", results.pop(0) if results else {"error": "boom"})
    monkeypatch.setattr(al, "execute_tool_block", _fake_exec, raising=False)

    outputs = list(round_outputs)
    prompts_seen = []

    async def _fake_stream(_candidates, messages, **kwargs):
        prompts_seen.append(json.dumps(messages))
        text = outputs.pop(0) if outputs else ""
        if text:
            yield f'data: {json.dumps({"delta": text})}\n\n'
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)

    gen = al.stream_agent_loop(
        "http://localhost:11434/v1", "qwen3.5:9b-32k",
        [{"role": "user", "content": "fact check and correct the document"}],
        max_rounds=max_rounds,
        relevant_tools={"edit_document", "update_document"},
    )
    return _collect(gen), prompts_seen, calls


EDIT_FENCE = "```edit_document\n<<<FIND>>>\n20-30°C\n<<<REPLACE>>>\n24-30°C\n<<<END>>>\n```"
EMPTY_ERROR = {"error": "edit_document received no content — the call carried no "
                        "FIND/REPLACE blocks at all.", "exit_code": 1}


def test_failed_edit_feeds_the_retry_directive_into_the_next_round(monkeypatch):
    """The directive has to reach the model, not just the log."""
    _, prompts, _ = _run_loop(
        monkeypatch,
        round_outputs=[EDIT_FENCE, "I give up."],
        tool_results=[EMPTY_ERROR],
    )
    assert len(prompts) >= 2, "model was never given a second round"
    second = prompts[1]
    assert "THE EDIT DID NOT HAPPEN" in second
    assert "<<<FIND>>>" in second
    assert "do not end the turn" in second.lower()


def test_second_failure_escalates_to_update_document_in_the_prompt(monkeypatch):
    """Escalation must count across rounds, not reset per round."""
    _, prompts, _ = _run_loop(
        monkeypatch,
        round_outputs=[EDIT_FENCE, EDIT_FENCE, "Sorry."],
        tool_results=[EMPTY_ERROR, EMPTY_ERROR],
    )
    assert len(prompts) >= 3
    assert "failed 2 times" in prompts[2]
    assert "update_document" in prompts[2]


def test_silent_failed_turn_tells_the_user_instead_of_done(monkeypatch):
    """The b5fe4ef5 shape end-to-end: edit fails, model then says nothing.

    Pre-fix this reached routes/chat_routes.py with an empty response and a
    non-empty tool_events list, and was saved as "Done.".
    """
    chunks, _, _ = _run_loop(
        monkeypatch,
        round_outputs=[EDIT_FENCE, ""],
        tool_results=[EMPTY_ERROR],
        max_rounds=2,
    )
    text = _deltas(chunks)
    assert "document is unchanged" in text.lower()
    assert text.strip() != "Done."


def test_false_success_claim_is_contradicted(monkeypatch):
    """Model asserts it corrected the document; the edit actually failed."""
    chunks, _, _ = _run_loop(
        monkeypatch,
        round_outputs=[EDIT_FENCE, "I've corrected the temperature ranges."],
        tool_results=[EMPTY_ERROR],
        max_rounds=2,
    )
    text = _deltas(chunks)
    assert "I've corrected the temperature ranges." in text
    assert "document is unchanged" in text.lower()


def test_successful_silent_edit_reports_what_changed(monkeypatch):
    """Run 009660d2's shape: edit succeeds, model writes nothing.

    Verifies the split gate end-to-end on a NON-finetune model — this is the
    path that used to be dead code and produced a bare "Done.".
    """
    chunks, _, _ = _run_loop(
        monkeypatch,
        round_outputs=[EDIT_FENCE, ""],
        tool_results=[{
            "action": "edit", "doc_id": "d1", "title": "Pink Oyster Mushroom Growth Phases",
            "content": "corrected document body", "language": "markdown",
            "version": 2, "applied": 7, "skipped": 0, "stale_values": [],
        }],
        max_rounds=2,
    )
    text = _deltas(chunks)
    assert "Pink Oyster Mushroom Growth Phases" in text
    assert "v2" in text and "7 edits applied" in text
    assert text.strip() != "Done."


def test_stale_value_warning_reaches_the_stream(monkeypatch):
    """The half-corrected document. Previously logs-only on this model."""
    chunks, _, _ = _run_loop(
        monkeypatch,
        round_outputs=[EDIT_FENCE, ""],
        tool_results=[{
            "action": "edit", "doc_id": "d1", "title": "Guide", "version": 4,
            "content": "body", "language": "markdown",
            "applied": 9, "skipped": 0, "stale_values": ["0.4%"],
        }],
        max_rounds=2,
    )
    text = _deltas(chunks)
    assert "Still inconsistent" in text
    assert "`0.4%`" in text
    assert "contradicts itself" in text


def test_gathering_only_turn_does_not_end_as_done(monkeypatch):
    """Run 0b12aadb end-to-end: read the file, then say nothing.

    Not a document turn at all — this is the same "Done." shape on the
    read-only tool path, which the document fix did not cover.
    """
    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)
    # Merged 2026-10-06: upstream's untrusted-context gate treats any tool
    # result that carries text — an edit_document error included — as content
    # that arms it, after which a second document edit needs a sealed user
    # approval. These tests pin the end-of-turn report, not the gate (upstream
    # covers that in tests/test_external_context_tool_gate.py), so the gate is
    # held open here.
    from src.tool_capabilities import ToolGateDecision, ToolRunSecurityContext
    monkeypatch.setattr(
        ToolRunSecurityContext, "decision_for",
        lambda self, tool_name, content=None: ToolGateDecision(True),
    )

    async def _fake_exec(block, *a, **k):
        return ("read_file", {"output": "// HTML page\nvoid htmlMain() {...}", "exit_code": 0})
    monkeypatch.setattr(al, "execute_tool_block", _fake_exec, raising=False)

    outputs = ["```read_file\n/Users/c/martha9_1.ino\n```", ""]

    async def _fake_stream(_candidates, messages, **kwargs):
        text = outputs.pop(0) if outputs else ""
        if text:
            yield f'data: {json.dumps({"delta": text})}\n\n'
        yield "data: [DONE]\n\n"
    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)

    chunks = _collect(al.stream_agent_loop(
        "http://localhost:11434/v1", "qwen3.5:9b-32k",
        [{"role": "user", "content": "extract the html from martha9_1.ino and create index.html"}],
        max_rounds=2, relevant_tools={"read_file", "write_file"},
    ))
    text = _deltas(chunks)
    assert text.strip() != "Done."
    assert "nothing was created or changed" in text.lower()
    assert "`read_file`" in text


def test_recovery_after_a_failure_reports_success_not_failure(monkeypatch):
    """Fail, then succeed. The turn must not carry the failure notice."""
    chunks, _, _ = _run_loop(
        monkeypatch,
        round_outputs=[EDIT_FENCE, EDIT_FENCE, ""],
        tool_results=[EMPTY_ERROR, {
            "action": "edit", "doc_id": "d1", "title": "Guide",
            "content": "body", "language": "markdown",
            "version": 3, "applied": 4, "skipped": 0, "stale_values": [],
        }],
        max_rounds=3,
    )
    text = _deltas(chunks)
    assert "4 edits applied" in text
    assert "couldn't apply the edit" not in text.lower()
