"""Tests for Ollama /v1 thinking-suppression helpers.

Covers:
- _is_ollama_openai_compat_url: URL classification (local host + /v1 path)
- think: false is injected into the payload for Ollama /v1 thinking models
- think: false is NOT injected for non-thinking models or non-Ollama /v1 endpoints
"""
import asyncio
import json

from src import llm_core


# ---------------------------------------------------------------------------
# Fake HTTP client — captures the outgoing payload without network I/O
# ---------------------------------------------------------------------------

class _FakeResp:
    status_code = 200

    async def aiter_lines(self):
        # Yield a minimal done event so stream_llm exits cleanly
        yield json.dumps({"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]})
        yield "data: [DONE]"

    async def aread(self):
        return b""


class _FakeStreamCtx:
    def __init__(self, captured):
        self._captured = captured

    async def __aenter__(self):
        return _FakeResp()

    async def __aexit__(self, *a):
        return False


class _FakeClient:
    """Minimal stand-in for httpx.AsyncClient that captures request payload."""

    def __init__(self):
        self.captured_payload = {}

    def stream(self, method, url, **kw):
        self.captured_payload = kw.get("json") or {}
        return _FakeStreamCtx(self.captured_payload)


def _capture_payload(monkeypatch, url, model):
    """Run stream_llm, intercept the HTTP payload, and return it."""
    client = _FakeClient()
    monkeypatch.setattr(llm_core, "_get_http_client", lambda: client)
    monkeypatch.setattr(llm_core, "_is_host_dead", lambda u: False)
    monkeypatch.setattr(llm_core, "note_model_activity", lambda *a, **k: None)
    monkeypatch.setattr(llm_core, "_clear_host_dead", lambda *a, **k: None)
    monkeypatch.setattr(llm_core, "get_context_length", lambda u, m: 32768)

    async def run():
        return [c async for c in llm_core.stream_llm(
            url, model, [{"role": "user", "content": "hi"}],
        )]

    asyncio.run(run())
    return client.captured_payload


# ---------------------------------------------------------------------------
# _is_ollama_openai_compat_url — pure function, no I/O
# ---------------------------------------------------------------------------

class TestIsOllamaOpenAICompatUrl:
    """Unit tests for the URL classifier that gates think-suppression."""

    # Positive cases — should be True
    def test_default_port_v1_root(self):
        assert llm_core._is_ollama_openai_compat_url("http://127.0.0.1:11434/v1")

    def test_default_port_chat_completions(self):
        assert llm_core._is_ollama_openai_compat_url("http://127.0.0.1:11434/v1/chat/completions")

    def test_localhost_default_port(self):
        assert llm_core._is_ollama_openai_compat_url("http://localhost:11434/v1")

    def test_localhost_default_port_with_path(self):
        assert llm_core._is_ollama_openai_compat_url("http://localhost:11434/v1/chat/completions")

    def test_loopback_ipv6(self):
        # IPv6 addresses in URLs require square brackets per RFC 3986
        assert llm_core._is_ollama_openai_compat_url("http://[::1]:11434/v1")

    def test_any_local_non_default_port(self):
        """Localhost on a non-default port (custom OLLAMA_HOST) must also match."""
        assert llm_core._is_ollama_openai_compat_url("http://127.0.0.1:11435/v1")

    def test_localhost_non_default_port(self):
        assert llm_core._is_ollama_openai_compat_url("http://localhost:8080/v1/chat/completions")

    def test_zero_dot_zero_host(self):
        assert llm_core._is_ollama_openai_compat_url("http://0.0.0.0:11434/v1")

    # Negative cases — should be False
    def test_openai_api_v1(self):
        """Real OpenAI endpoint must never match, even though path is /v1."""
        assert not llm_core._is_ollama_openai_compat_url("https://api.openai.com/v1")

    def test_openai_chat_completions(self):
        assert not llm_core._is_ollama_openai_compat_url("https://api.openai.com/v1/chat/completions")

    def test_ollama_native_api_path(self):
        """The native /api path is a different surface and must not match /v1."""
        assert not llm_core._is_ollama_openai_compat_url("http://localhost:11434/api")

    def test_ollama_native_api_chat(self):
        assert not llm_core._is_ollama_openai_compat_url("http://localhost:11434/api/chat")

    def test_remote_openrouter(self):
        assert not llm_core._is_ollama_openai_compat_url("https://openrouter.ai/api/v1")

    def test_empty_string(self):
        assert not llm_core._is_ollama_openai_compat_url("")

    def test_none_like_empty(self):
        assert not llm_core._is_ollama_openai_compat_url(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Payload injection — think: false only when both conditions hold
# ---------------------------------------------------------------------------

class TestThinkSuppression:
    """Assert think:false is present/absent in the outgoing HTTP payload."""

    def test_think_false_for_ollama_v1_thinking_model(self, monkeypatch):
        """think:false must be set for qwen3 on Ollama /v1."""
        payload = _capture_payload(
            monkeypatch, "http://127.0.0.1:11434/v1/chat/completions", "qwen3:14b"
        )
        assert payload.get("think") is False

    def test_no_think_for_ollama_v1_non_thinking_model(self, monkeypatch):
        """think must NOT be set for a plain (non-thinking) model on Ollama /v1."""
        payload = _capture_payload(
            monkeypatch, "http://127.0.0.1:11434/v1/chat/completions", "llama3.2:3b"
        )
        assert "think" not in payload

    def test_no_think_for_openai_endpoint_with_thinking_model_name(self, monkeypatch):
        """think must NOT leak to a real OpenAI endpoint even if the model name
        matches a thinking pattern — the URL guard is what matters."""
        payload = _capture_payload(
            monkeypatch, "https://api.openai.com/v1/chat/completions", "qwen3:14b"
        )
        assert "think" not in payload

    def test_think_false_for_non_default_port_thinking_model(self, monkeypatch):
        """Custom-port localhost Ollama (e.g. OLLAMA_HOST=0.0.0.0:11435) must
        also receive think:false — this is the regression guarded by the
        host-set check added in this fix."""
        payload = _capture_payload(
            monkeypatch, "http://127.0.0.1:11435/v1/chat/completions", "qwen3:14b"
        )
        assert payload.get("think") is False


# ---------------------------------------------------------------------------
# Native /api/chat agent rounds — think:false + /no_think for Qwen w/ tools
# ---------------------------------------------------------------------------

_TOOLS = [{"type": "function", "function": {"name": "web_search", "parameters": {}}}]


def _capture_native_payload(monkeypatch, model, *, tools=None, setting=True):
    """Run stream_llm against the native Ollama URL and capture the payload."""
    import src.settings as settings_mod

    client = _FakeClient()
    monkeypatch.setattr(llm_core, "_get_http_client", lambda: client)
    monkeypatch.setattr(llm_core, "_is_host_dead", lambda u: False)
    monkeypatch.setattr(llm_core, "note_model_activity", lambda *a, **k: None)
    monkeypatch.setattr(llm_core, "_clear_host_dead", lambda *a, **k: None)
    monkeypatch.setattr(llm_core, "get_context_length", lambda u, m: 32768)
    monkeypatch.setattr(
        settings_mod, "get_setting",
        lambda key, default=None: setting if key == "agent_disable_thinking" else default,
    )

    async def run():
        return [c async for c in llm_core.stream_llm(
            "http://127.0.0.1:11434/api/chat", model,
            [{"role": "system", "content": "You are an agent."},
             {"role": "user", "content": "hi"}],
            tools=tools,
        )]

    asyncio.run(run())
    return client.captured_payload


class TestNativeAgentThinkSuppression:
    """Agent rounds (tools passed) on native /api/chat suppress Qwen thinking."""

    def test_qwen_agent_round_gets_think_false(self, monkeypatch):
        payload = _capture_native_payload(monkeypatch, "qwen3:14b", tools=_TOOLS)
        assert payload.get("think") is False

    def test_qwen_agent_round_gets_no_think_soft_switch(self, monkeypatch):
        """Fallback for Ollama <0.9: /no_think appended to the system message."""
        payload = _capture_native_payload(monkeypatch, "qwen3:14b", tools=_TOOLS)
        sys_msg = payload["messages"][0]
        assert sys_msg["role"] == "system"
        assert sys_msg["content"].endswith("/no_think")

    def test_qwen_chat_round_keeps_thinking(self, monkeypatch):
        """No tools = normal chat round — thinking stays on."""
        payload = _capture_native_payload(monkeypatch, "qwen3:14b", tools=None)
        assert "think" not in payload
        assert "/no_think" not in payload["messages"][0]["content"]

    def test_non_qwen_agent_round_untouched(self, monkeypatch):
        """Ollama errors on `think` for non-thinking models — must not be sent."""
        payload = _capture_native_payload(monkeypatch, "llama3.2:3b", tools=_TOOLS)
        assert "think" not in payload
        assert "/no_think" not in payload["messages"][0]["content"]

    def test_setting_off_disables_suppression(self, monkeypatch):
        payload = _capture_native_payload(
            monkeypatch, "qwen3:14b", tools=_TOOLS, setting=False,
        )
        assert "think" not in payload
        assert "/no_think" not in payload["messages"][0]["content"]

    def test_qwq_agent_round_gets_think_false(self, monkeypatch):
        payload = _capture_native_payload(monkeypatch, "qwq:32b", tools=_TOOLS)
        assert payload.get("think") is False


class TestQwenModelDetection:
    def test_qwen3_variants(self):
        assert llm_core._is_qwen_thinking_model("qwen3:14b")
        assert llm_core._is_qwen_thinking_model("Qwen3.5-27B")
        assert llm_core._is_qwen_thinking_model("qwq:32b")

    def test_non_thinking_qwen_excluded(self):
        """qwen2.5 has no thinking capability — Ollama rejects a think param."""
        assert not llm_core._is_qwen_thinking_model("qwen2.5:7b")

    def test_other_models_excluded(self):
        assert not llm_core._is_qwen_thinking_model("gemma3:12b")
        assert not llm_core._is_qwen_thinking_model("llama3.2:3b")
        assert not llm_core._is_qwen_thinking_model("")


class TestBuildPayloadThinkParam:
    def test_think_false_emitted(self):
        p = llm_core._build_ollama_payload("qwen3:14b", [], 0.7, 100, think=False)
        assert p["think"] is False

    def test_think_omitted_by_default(self):
        p = llm_core._build_ollama_payload("qwen3:14b", [], 0.7, 100)
        assert "think" not in p


# ---------------------------------------------------------------------------
# /v1 compat path — reasoning_effort:"none" (think is ignored by stock Ollama)
# ---------------------------------------------------------------------------

def _capture_v1_payload(monkeypatch, model, *, tools=None, setting=True):
    import src.settings as settings_mod

    client = _FakeClient()
    monkeypatch.setattr(llm_core, "_get_http_client", lambda: client)
    monkeypatch.setattr(llm_core, "_is_host_dead", lambda u: False)
    monkeypatch.setattr(llm_core, "note_model_activity", lambda *a, **k: None)
    monkeypatch.setattr(llm_core, "_clear_host_dead", lambda *a, **k: None)
    monkeypatch.setattr(llm_core, "get_context_length", lambda u, m: 32768)
    monkeypatch.setattr(
        settings_mod, "get_setting",
        lambda key, default=None: setting if key == "agent_disable_thinking" else default,
    )

    async def run():
        return [c async for c in llm_core.stream_llm(
            "http://127.0.0.1:11434/v1/chat/completions", model,
            [{"role": "user", "content": "hi"}],
            tools=tools,
        )]

    asyncio.run(run())
    return client.captured_payload


class TestV1ReasoningEffortSuppression:
    """Ollama /v1 silently ignores `think`; reasoning_effort:"none" is the
    documented control (docs.ollama.com/api/openai-compatibility). Sent for
    Qwen thinking models in agent/tool rounds, gated by the setting."""

    def test_qwen_agent_round_gets_reasoning_effort_none(self, monkeypatch):
        payload = _capture_v1_payload(monkeypatch, "qwen3.5:4b-32k", tools=_TOOLS)
        assert payload.get("reasoning_effort") == "none"
        assert payload.get("think") is False  # legacy field kept

    def test_qwen_chat_round_keeps_thinking(self, monkeypatch):
        payload = _capture_v1_payload(monkeypatch, "qwen3.5:4b-32k", tools=None)
        assert "reasoning_effort" not in payload

    def test_setting_off_disables_reasoning_effort(self, monkeypatch):
        payload = _capture_v1_payload(
            monkeypatch, "qwen3.5:4b-32k", tools=_TOOLS, setting=False,
        )
        assert "reasoning_effort" not in payload

    def test_gemma_never_gets_reasoning_effort(self, monkeypatch):
        """gemma matches the broad thinking-pattern list but Ollama may reject
        reasoning_effort on non-thinking gemma variants — must not be sent."""
        payload = _capture_v1_payload(monkeypatch, "gemma3:12b", tools=_TOOLS)
        assert "reasoning_effort" not in payload

    def test_openai_endpoint_never_gets_reasoning_effort(self, monkeypatch):
        client = _FakeClient()
        monkeypatch.setattr(llm_core, "_get_http_client", lambda: client)
        monkeypatch.setattr(llm_core, "_is_host_dead", lambda u: False)
        monkeypatch.setattr(llm_core, "note_model_activity", lambda *a, **k: None)
        monkeypatch.setattr(llm_core, "_clear_host_dead", lambda *a, **k: None)

        async def run():
            return [c async for c in llm_core.stream_llm(
                "https://api.openai.com/v1/chat/completions", "qwen3:14b",
                [{"role": "user", "content": "hi"}], tools=_TOOLS,
            )]

        asyncio.run(run())
        assert "reasoning_effort" not in client.captured_payload
