"""A local model named with a "-16k"-style suffix declares its served num_ctx.

Observed 2026-07-16: `qwen3.5:4b-16k` was created with `PARAMETER num_ctx
16384` (setup doc config #1), but Ollama reports no context window (no /slots,
nothing on /v1/models), so `_query_context_length` fell back to the
known-models table's architecture max (131072). Context trimming then budgeted
against a window 8x larger than served — Ollama silently truncates the prompt
TOP (system prompt + skills) once a turn crosses 16k. `ollama show` confirmed
num_ctx 16384; the server log confirmed n_ctx_slot=16384; the UI showed
131,072.

Fix under test: for LOCAL endpoints the name suffix beats the known table.
Endpoint-reported values (llama.cpp /slots, /v1/models context fields) still
beat the suffix.
"""

import httpx
import pytest

import src.model_context as mc


@pytest.mark.parametrize("name,expected", [
    ("qwen3.5:4b-16k", 16384),
    ("qwen3.5:9b-16k", 16384),
    ("qwen3:8b-32k", 32768),
    ("some_model_128k", 131072),
    ("gpt-4-32k", 32768),
    ("qwen3.5:4b", None),          # no suffix
    ("mixtral-8x7b", None),        # 'b' suffix, not 'k'
    ("llama-3-8b", None),
    ("", None),
])
def test_ctx_from_name_suffix(name, expected):
    assert mc._ctx_from_name_suffix(name) == expected


@pytest.fixture
def _no_network(monkeypatch):
    """Local endpoint that reports nothing: /slots and /v1/models both fail."""
    def _raise(*a, **k):
        raise httpx.ConnectError("no network in tests")
    monkeypatch.setattr(mc.httpx, "get", _raise)
    monkeypatch.setattr(mc, "_configured_endpoint_kind", lambda url: None)


def test_local_suffix_overrides_known_table(_no_network):
    ctx, known = mc._query_context_length("http://localhost:11434/v1", "qwen3.5:4b-16k")
    assert ctx == 16384
    assert known is True


def test_local_without_suffix_still_uses_known_table(_no_network):
    # Plain model id keeps the previous behaviour (known table).
    ctx, known = mc._query_context_length("http://localhost:11434/v1", "qwen3.5:4b")
    assert ctx == mc._lookup_known("qwen3.5:4b")
    assert known is True


def test_remote_endpoint_ignores_suffix(_no_network, monkeypatch):
    # A public/remote endpoint must not treat the suffix as a local num_ctx
    # declaration — "gpt-4-32k" etc. are covered by the known table.
    monkeypatch.setattr(mc, "is_local_endpoint", lambda url: False)
    ctx, known = mc._query_context_length("https://api.example.com/v1", "qwen3.5:4b-16k")
    assert ctx == mc._lookup_known("qwen3.5:4b-16k")
    assert known is True


def test_endpoint_report_beats_suffix(monkeypatch):
    # llama.cpp /slots reports the ACTUAL serving context — it must win over
    # the name suffix (a stale name should not override a live report).
    class _Resp:
        is_success = True
        def json(self):
            return [{"n_ctx": 8192}]
    monkeypatch.setattr(mc.httpx, "get", lambda *a, **k: _Resp())
    monkeypatch.setattr(mc, "_configured_endpoint_kind", lambda url: None)
    ctx, known = mc._query_context_length("http://localhost:8000/v1", "some-model-16k")
    assert ctx == 8192
    assert known is True
