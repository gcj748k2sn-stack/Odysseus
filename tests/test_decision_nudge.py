"""Local models get a fixed "decide, then act" rule in the system message.

Covers ``src/decision_nudge.py`` and its call site in ``stream_agent_loop``
(after ``_build_system_prompt`` for each route).
"""

import asyncio
import inspect
import json

import pytest

from src.decision_nudge import DECISION_RULE, apply

_SYSTEM = {"role": "system", "content": "## Base rules\n- be brief"}
_USER = {"role": "user", "content": "hi"}


@pytest.mark.parametrize("url", [
    "http://localhost:8090/v1",
    "http://127.0.0.1:1234/v1",
    "http://192.168.1.20:8000/v1",
    "http://mac-studio.local:1234/v1",
])
def test_local_endpoints_get_the_rule_once(url):
    out = apply([_SYSTEM, _USER], url)
    assert out[0]["content"].endswith(DECISION_RULE)
    assert out[1] is _USER
    assert apply(out, url)[0]["content"].count("## Deciding") == 1
    assert _SYSTEM["content"] == "## Base rules\n- be brief", "input must not be mutated"


@pytest.mark.parametrize("messages, url", [
    ([_SYSTEM, _USER], "https://api.openai.com/v1"),
    ([_SYSTEM, _USER], "https://openrouter.ai/api/v1"),
    ([_USER], "http://localhost:8090/v1"),
    ([], "http://localhost:8090/v1"),
    ([{"role": "system", "content": [{"type": "text", "text": "x"}]}], "http://localhost:8090/v1"),
])
def test_everything_else_is_unchanged(messages, url):
    assert apply(messages, url) is messages


def _system_sent(monkeypatch, url):
    import src.agent_loop as agent_loop

    monkeypatch.setattr(agent_loop, "get_setting", lambda k, d=None: d, raising=False)
    monkeypatch.setattr(agent_loop, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(agent_loop, "estimate_tokens", lambda *a, **k: 10)
    seen = []

    async def fake_stream(candidates, _messages, **kwargs):
        # The request the provider would receive, not the loop's working list.
        request = kwargs["candidate_request_factory"](0, *candidates[0])
        if inspect.isawaitable(request):
            request = await request
        seen.append([dict(m) for m in request["messages"]])
        yield "data: " + json.dumps({"delta": "4"}) + "\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(agent_loop, "stream_llm_with_fallback", fake_stream)

    async def run():
        return [c async for c in agent_loop.stream_agent_loop(
            url, "some-model", [{"role": "user", "content": "what is 2+2"}],
            max_rounds=1, relevant_tools={"read_file"},
        )]

    asyncio.run(run())
    assert seen, "the model was never called"
    system = "\n".join(
        str(m.get("content")) for m in seen[0] if m.get("role") == "system"
    )
    assert "## " in system, "no agent system prompt was sent (wrong code path)"
    return system


def test_loop_sends_the_rule_to_a_local_model(monkeypatch):
    assert "## Deciding" in _system_sent(monkeypatch, "http://localhost:8090/v1")


def test_loop_leaves_remote_models_alone(monkeypatch):
    assert "## Deciding" not in _system_sent(monkeypatch, "https://api.openai.com/v1")
