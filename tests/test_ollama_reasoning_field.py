"""Prior-round reasoning must reach Ollama's /v1 under the field it reads.

notes/todo.md, *"The model finishes the job in the reasoning channel, and the
guard calls it silence"*. Ollama's OpenAI-compatible ``Message`` reads
``reasoning`` and silently drops ``reasoning_content`` (the DeepSeek name the
agent loop uses). With thinking on, Ollama's Qwen 3.5 renderer then wrapped
every earlier tool round of the turn in an EMPTY ``<think>\\n\\n</think>`` —
Qwen's thinking-disabled marker. Measured 2026-10-02 on Ollama 0.31.1:
``_debug_render_only`` showed 3 empty blocks for a 3-round turn, and replaying
that turn the model drafted its answer inside the open think block in 11 of 12
runs (0 of 12 with the reasoning present).

These tests pin the outgoing request, not the model: Ollama /v1 + Qwen gets
``reasoning`` on EVERY round of the turn, and every other provider/model gets
exactly what it got before (negative controls).
"""
import asyncio

import src.agent_loop as al
from src import llm_core

OLLAMA_V1 = "http://localhost:11434/v1/chat/completions"
QWEN = "qwen3.5:9b-64k"
REASONING = [
    "R1: the user wants current news, search first.",
    "R2: results are local, fetch the bulletin.",
    "R3: fetch failed, search broader.",
]


def _turn():
    """A three-round tool turn built by the real _append_tool_results."""
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "what's happening in the world"},
    ]
    for k, r in enumerate(REASONING, start=1):
        call = [{"id": f"call_{k}", "name": "web_search", "arguments": '{"query": "q%d"}' % k}]
        al._append_tool_results(messages, "", call, [{}], [f"result {k}"], True, k, round_reasoning=r)
    return messages


def _assistants(msgs):
    return [m for m in msgs if m.get("role") == "assistant"]


def _captured_stream_payload(monkeypatch, url, model, messages):
    """Run stream_llm far enough to build the payload, then stop before HTTP."""
    seen = {}

    def spy(payload, target_url, model_):
        seen["payload"] = payload

    monkeypatch.setattr(llm_core, "_scrub_openai_chat_tool_reasoning", spy)
    monkeypatch.setattr(llm_core, "_is_host_dead", lambda url: True)

    async def run():
        return [c async for c in llm_core.stream_llm(
            url, model, messages, temperature=0.6, max_tokens=64,
            tools=[{"type": "function", "function": {"name": "web_search", "parameters": {}}}],
        )]

    asyncio.run(run())
    return seen["payload"]


def test_every_round_keeps_its_own_reasoning():
    asst = _assistants(_turn())
    assert [m.get("_turn_reasoning") for m in asst] == REASONING
    # Unchanged behaviour for DeepSeek/Nemotron: only the newest keeps reasoning_content.
    assert [("reasoning_content" in m) for m in asst] == [False, False, True]


def test_ollama_v1_qwen_payload_carries_reasoning_on_every_round(monkeypatch):
    payload = _captured_stream_payload(monkeypatch, OLLAMA_V1, QWEN, _turn())
    asst = _assistants(payload["messages"])
    assert [m.get("reasoning") for m in asst] == REASONING
    for m in asst:
        assert "reasoning_content" not in m
        assert "_turn_reasoning" not in m
        assert m["tool_calls"]


def test_non_streaming_paths_map_the_same_way():
    mapped = llm_core._sanitize_llm_messages(
        llm_core._map_reasoning_for_ollama_compat(_turn(), OLLAMA_V1, QWEN))
    assert [m.get("reasoning") for m in _assistants(mapped)] == REASONING


def test_input_messages_are_not_mutated():
    msgs = _turn()
    before = [dict(m) for m in msgs]
    llm_core._map_reasoning_for_ollama_compat(msgs, OLLAMA_V1, QWEN)
    assert msgs == before


# --- negative controls: nothing changes outside Ollama /v1 + Qwen ----------

def test_control_deepseek_unchanged(monkeypatch):
    payload = _captured_stream_payload(monkeypatch, "https://api.deepseek.com/v1", "deepseek-reasoner", _turn())
    asst = _assistants(payload["messages"])
    assert [m.get("reasoning_content") for m in asst] == [None, None, REASONING[2]]
    assert all("reasoning" not in m and "_turn_reasoning" not in m for m in asst)


def test_control_non_qwen_model_on_ollama_unchanged(monkeypatch):
    payload = _captured_stream_payload(monkeypatch, OLLAMA_V1, "llama3.1:8b", _turn())
    asst = _assistants(payload["messages"])
    assert [m.get("reasoning_content") for m in asst] == [None, None, REASONING[2]]
    assert all("reasoning" not in m and "_turn_reasoning" not in m for m in asst)


def test_control_no_reasoning_adds_no_field():
    msgs = [{"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"}]
    mapped = llm_core._map_reasoning_for_ollama_compat(msgs, OLLAMA_V1, QWEN)
    assert mapped[1] == {"role": "assistant", "content": "hello"}
