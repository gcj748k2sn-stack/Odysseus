"""The direct low-signal reply path leaves room for a thinking model's answer.

notes/todo.md, *"A plain question in a new chat without a workspace gets a
128-token reply cap"*. The benchmark's ``explain`` task (no workspace since the
2026-10-09 suite rebuild) took the direct path; ``min(max_tokens or 128, 128)``
let Qwen's thinking use every token and the answer came back empty, 2 of 2.

Covers ``src/direct_reply.py`` and its call site in ``stream_agent_loop``.

Item 76 (notes/todo.md, *"Direct reply path: no system prompt, long
thinking"*): the same path sent the question alone; Qwen then thought 7,000–
16,000 chars and often used the whole cap. With Odysseus's own system prompt it
thought 285–1,500 (scripts/probe_direct_reply.py, 2026-10-09). A real question
now gets that prompt; a greeting stays bare, as upstream sends it.
"""

import asyncio
import json

import pytest

from src.direct_reply import DEFAULT_MAX_TOKENS, max_tokens, messages

_EXPLAIN = (
    "In at most three sentences: what is the difference between RAM and flash "
    "memory on a microcontroller like the ESP32?"
)


@pytest.mark.parametrize("requested, expected", [
    (None, DEFAULT_MAX_TOKENS),
    (0, DEFAULT_MAX_TOKENS),
    (-1, DEFAULT_MAX_TOKENS),
    ("junk", DEFAULT_MAX_TOKENS),
    (8192, 8192),
    (300, 300),
])
def test_cap_uses_the_requested_limit_or_a_roomy_default(requested, expected):
    assert max_tokens(requested) == expected


def test_default_leaves_room_for_thinking():
    assert DEFAULT_MAX_TOKENS >= 2048


def test_messages_add_the_system_prompt_for_a_question():
    assert messages("why?", False, "SYS") == [{"role": "system", "content": "SYS"},
                                              {"role": "user", "content": "why?"}]


def test_messages_leave_a_greeting_bare():
    assert messages("hi", True, "SYS") == [{"role": "user", "content": "hi"}]
    assert messages("why?", False, "") == [{"role": "user", "content": "why?"}]


def _direct_call(monkeypatch, question=_EXPLAIN, **loop_kwargs):
    import src.agent_loop as agent_loop

    monkeypatch.setattr(agent_loop, "get_setting", lambda k, d=None: d, raising=False)
    monkeypatch.setattr(agent_loop, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(agent_loop, "estimate_tokens", lambda *a, **k: 10)
    calls = []

    async def fake_stream(candidates, messages, **kwargs):
        calls.append({"messages": messages, **kwargs})
        yield "data: " + json.dumps({"delta": "RAM is volatile; flash keeps data."}) + "\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(agent_loop, "stream_llm_with_fallback", fake_stream)

    async def run():
        return [c async for c in agent_loop.stream_agent_loop(
            "http://localhost:1234/v1", "qwen/qwen3.5-9b",
            [{"role": "user", "content": question}], max_rounds=1, **loop_kwargs,
        )]

    asyncio.run(run())
    assert len(calls) == 1, "expected exactly one model call"
    call = calls[0]
    assert call.get("tools") is None and call["messages"][-1] == {"role": "user", "content": question}, \
        "this question must take the direct reply path, or the test proves nothing"
    return call


def test_plain_question_gets_odysseus_system_prompt(monkeypatch):
    from src.agent_loop import _assemble_prompt

    sent = _direct_call(monkeypatch)["messages"]
    assert len(sent) == 2 and sent[0]["role"] == "system"
    assert sent[0]["content"] == _assemble_prompt(set(), compact=True)
    assert "Keep answers concise" in sent[0]["content"]


def test_greeting_on_the_direct_path_stays_bare(monkeypatch):
    assert _direct_call(monkeypatch, question="hello")["messages"] == [{"role": "user", "content": "hello"}]


def test_plain_question_in_new_chat_is_not_capped_at_128(monkeypatch):
    assert _direct_call(monkeypatch)["max_tokens"] == DEFAULT_MAX_TOKENS


def test_preset_limit_is_respected_on_the_direct_path(monkeypatch):
    assert _direct_call(monkeypatch, max_tokens=8192)["max_tokens"] == 8192
