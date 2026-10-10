"""Local servers get every tool round's thinking back, so each request extends the last.

Covers ``src/turn_reasoning.py`` and its call site at the top of
``_trim_route_request_messages`` in ``stream_agent_loop``.
"""

import asyncio
import inspect
import json

import pytest

from src.turn_reasoning import HEAD_CHARS, MARK, MAX_CHARS, apply, shorten

LOCAL = "http://localhost:8090/v1/chat/completions"
REMOTE = "https://api.openai.com/v1/chat/completions"


def _assistant(thinking, keep_visible=False):
    m = {"role": "assistant", "content": None, "_turn_reasoning": thinking,
         "tool_calls": [{"id": "c", "type": "function", "function": {"name": "f", "arguments": "{}"}}]}
    if keep_visible:
        m["reasoning_content"] = thinking
    return m


def test_restores_popped_thinking_on_local_endpoints_without_mutating():
    old, new = _assistant("first plan"), _assistant("second plan", keep_visible=True)
    msgs = [{"role": "user", "content": "q"}, old, {"role": "tool", "content": "r"}, new]
    out = apply(msgs, LOCAL)
    assert out[1]["reasoning_content"] == "first plan"
    assert out[3] is new
    assert "reasoning_content" not in old, "input must not be mutated"


@pytest.mark.parametrize("url", [REMOTE, "https://openrouter.ai/api/v1"])
def test_remote_endpoints_are_untouched(url):
    msgs = [_assistant("plan")]
    assert apply(msgs, url) is msgs


def test_history_messages_without_turn_thinking_are_untouched():
    msgs = [{"role": "assistant", "content": "earlier answer"}, {"role": "user", "content": "q"}]
    assert apply(msgs, LOCAL) is msgs


def test_shorten_is_bounded_and_deterministic():
    text = "".join(f"{i:05d} " for i in range(3000))
    short = shorten(text)
    assert len(short) == MAX_CHARS
    assert short.startswith(text[:HEAD_CHARS]) and short.endswith(text[-200:]) and MARK in short
    assert shorten(text) == short
    assert shorten("tiny") == "tiny"
    assert apply([_assistant(text)], LOCAL)[0]["reasoning_content"] == short


_VISIBLE = ("role", "content", "tool_calls", "tool_call_id", "reasoning_content")


def _requests(monkeypatch, url, model):
    import src.agent_loop as al

    monkeypatch.setattr(al, "get_setting", lambda k, d=None: d, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)
    monkeypatch.setattr(al, "blocked_tools_for_owner", lambda owner: set(), raising=False)

    async def fake_exec(block, *a, **k):
        return ("read_file", {"output": "file text", "exit_code": 0})

    monkeypatch.setattr(al, "execute_tool_block", fake_exec, raising=False)
    seen = []

    async def fake_stream(candidates, _messages, **kwargs):
        request = kwargs["candidate_request_factory"](0, *candidates[0])
        if inspect.isawaitable(request):
            request = await request
        seen.append([{k: m[k] for k in _VISIBLE if k in m} for m in request["messages"]])
        n = len(seen)
        if n <= 3:
            yield "data: " + json.dumps({"delta": f"plan {n}", "thinking": True}) + "\n\n"
            calls = [{"id": f"call_{n}", "name": "read_file",
                      "arguments": json.dumps({"path": f"/tmp/f{n}.txt"})}]
            yield "data: " + json.dumps({"type": "tool_calls", "calls": calls}) + "\n\n"
        else:
            yield "data: " + json.dumps({"delta": "done"}) + "\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "stream_llm_with_fallback", fake_stream)

    async def run():
        return [c async for c in al.stream_agent_loop(
            url, model, [{"role": "user", "content": "read three files"}],
            max_rounds=5, relevant_tools={"read_file"},
        )]

    asyncio.run(run())
    assert len(seen) == 4, f"expected 4 model calls, got {len(seen)}"
    return seen


def _thinking_of_tool_rounds(request):
    return [m.get("reasoning_content") for m in request if m.get("tool_calls")]


def test_loop_sends_every_round_its_thinking_to_a_local_server(monkeypatch):
    seen = _requests(monkeypatch, LOCAL, "bonsai2-27b")
    assert _thinking_of_tool_rounds(seen[3]) == ["plan 1", "plan 2", "plan 3"]
    for before, after in zip(seen[1:], seen[2:]):
        # what the server already read is sent again unchanged
        body_before = before
        body_after = after
        assert body_after[:len(body_before)] == body_before


def test_loop_keeps_the_old_behaviour_for_remote_models(monkeypatch):
    seen = _requests(monkeypatch, REMOTE, "gpt-4o")
    assert _thinking_of_tool_rounds(seen[3]) == [None, None, "plan 3"]
