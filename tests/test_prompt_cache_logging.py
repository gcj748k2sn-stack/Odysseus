"""Per-round prompt-cache figures on the `round_stream_done` line.

docs/todo.md items 40, 57 and 58 all turn on one question nothing recorded:
how much of each request's prompt did the local server reuse from its KV
cache? llama.cpp reports it in the final chunk's `timings` (`cache_n` reused,
`prompt_n` processed now, `prompt_ms`); OpenAI-style servers in
`usage.prompt_tokens_details.cached_tokens`. Both are now carried on the
usage event and logged per round as
`… finish_reason=… prompt_tokens=… cache_n=… prompt_n=… prompt_ms=…`.
"""
import asyncio
import json
import logging

import pytest

import src.agent_loop as al
import src.tool_index as tool_index
from src import llm_core
from tests.test_chat_metrics import _usage_event


def _final_chunk(**extra):
    chunk = {"choices": [], "object": "chat.completion.chunk",
             "usage": {"prompt_tokens": 3261, "completion_tokens": 40}}
    chunk.update(extra)
    return ['data: ' + json.dumps({"choices": [{"index": 0, "delta": {"content": "ok"}}]}),
            'data: ' + json.dumps(chunk), "data: [DONE]"]


# ── llm_core: the usage event carries the figures ──

def test_llamacpp_timings_reach_the_usage_event(monkeypatch):
    usage = _usage_event(monkeypatch, _final_chunk(timings={
        "cache_n": 3204, "prompt_n": 57, "prompt_ms": 812.345,
        "prompt_per_second": 70.2, "predicted_n": 40, "predicted_per_second": 11.9,
    }))
    assert usage["cache_n"] == 3204
    assert usage["prompt_n"] == 57
    assert usage["prompt_ms"] == 812.3
    assert usage["gen_tps"] == 11.9  # existing fields untouched


def test_openai_style_cached_tokens(monkeypatch):
    chunk = _final_chunk()
    payload = json.loads(chunk[1][6:])
    payload["usage"]["prompt_tokens_details"] = {"cached_tokens": 3072}
    chunk[1] = "data: " + json.dumps(payload)
    usage = _usage_event(monkeypatch, chunk)
    assert usage["cached_tokens"] == 3072
    assert "cache_n" not in usage


def test_nothing_reported_means_nothing_invented(monkeypatch):
    """Negative control: no `timings`, no details → no cache keys at all."""
    usage = _usage_event(monkeypatch, _final_chunk())
    assert usage["input_tokens"] == 3261
    assert not {"cache_n", "prompt_n", "prompt_ms", "cached_tokens"} & set(usage)


@pytest.mark.parametrize("bad", [True, -1, "12", None, [3]])
def test_malformed_values_are_dropped(bad):
    fields = llm_core._prompt_cache_fields({
        "timings": {"cache_n": bad, "prompt_n": bad, "prompt_ms": bad},
        "usage": {"prompt_tokens_details": {"cached_tokens": bad}},
    })
    assert fields == {}


def test_zero_cache_is_reported_as_zero():
    """A full re-read is the finding items 57/58 are about — 0, not absent."""
    assert llm_core._prompt_cache_fields({"timings": {"cache_n": 0, "prompt_n": 3261}}) == {
        "cache_n": 0, "prompt_n": 3261,
    }


# ── agent_loop: the log line ──

def test_format_prompt_cache():
    assert al._format_prompt_cache(
        {"prompt_tokens": 3261, "cache_n": 3204, "prompt_n": 57, "prompt_ms": 812.3}
    ) == " prompt_tokens=3261 cache_n=3204 prompt_n=57 prompt_ms=812.3"
    assert al._format_prompt_cache(None) == " prompt_tokens=? cache_n=? prompt_n=? prompt_ms=?"
    assert al._format_prompt_cache({"prompt_tokens": 9, "cached_tokens": 8}) == (
        " prompt_tokens=9 cache_n=? prompt_n=? prompt_ms=? cached_tokens=8"
    )


class _FakeIndex:
    def index_mcp_tools(self, *a, **k):
        return None

    def get_tools_for_query(self, query, k=8, always_include=None):
        return set(tool_index.ALWAYS_AVAILABLE) | {"web_search"}


def _round_lines(monkeypatch, caplog, usage):
    async def _fake_stream(_candidates, messages, **kw):
        yield "data: " + json.dumps({"delta": "ok"}) + "\n\n"
        if usage is not None:
            yield "data: " + json.dumps({"type": "usage", "data": usage}) + "\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(al, "blocked_tools_for_owner", lambda owner: set(), raising=False)
    monkeypatch.setattr(al, "_load_mcp_disabled_map", lambda: {}, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)
    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)
    monkeypatch.setattr(al, "configured_machine_names", lambda: frozenset())
    monkeypatch.setattr(tool_index, "get_tool_index", lambda: _FakeIndex())
    caplog.set_level(logging.INFO, logger=al.logger.name)

    async def _run():
        return [c async for c in al.stream_agent_loop(
            "http://localhost:8090/v1", "bonsai2-27b",
            [{"role": "user", "content": "search the web for dragonfly facts"}],
            max_rounds=1,
        )]

    asyncio.run(_run())
    return [r.getMessage() for r in caplog.records if "round_stream_done" in r.getMessage()]


def test_round_line_carries_the_cache_figures(monkeypatch, caplog):
    lines = _round_lines(monkeypatch, caplog, {
        "input_tokens": 3261, "output_tokens": 40,
        "cache_n": 3204, "prompt_n": 57, "prompt_ms": 812.3,
    })
    assert len(lines) == 1
    assert lines[0].endswith("prompt_tokens=3261 cache_n=3204 prompt_n=57 prompt_ms=812.3")
    assert "finish_reason=" in lines[0]  # the item 41 field is still there


def test_round_without_usage_says_so(monkeypatch, caplog):
    lines = _round_lines(monkeypatch, caplog, None)
    assert len(lines) == 1
    assert lines[0].endswith("prompt_tokens=? cache_n=? prompt_n=? prompt_ms=?")
