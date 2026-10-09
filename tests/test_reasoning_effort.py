"""The custom preset's reasoning effort reaches llama.cpp on every request.

Bonsai 2's thinking length is set by its chat template's `reasoning_effort`
(xhigh by default, medium much shorter). The preset field is resolved once per
chat request and added as `chat_template_kwargs` to each model request of the
turn, for local OpenAI-compatible servers only: cloud APIs reject unknown
fields.
"""
import asyncio
import contextvars
import json

import pytest
from pydantic import ValidationError

from src import llm_core
from src import reasoning_effort as RE
from src.preset_manager import PresetManager
from src.request_models import PresetUpdateRequest


# --- the module itself ---------------------------------------------------------

def test_from_preset_reads_a_known_value():
    assert RE.from_preset({"reasoning_effort": "Medium"}) == "medium"
    assert RE.from_preset({"reasoning_effort": "xhigh"}) == "xhigh"


@pytest.mark.parametrize("preset", [
    None,
    {},
    {"reasoning_effort": ""},
    {"reasoning_effort": "extreme"},
    # Bonsai 2's template raises on "high", which would fail every request.
    {"reasoning_effort": "high"},
    {"reasoning_effort": "medium", "enabled": False},
])
def test_from_preset_gives_nothing_for_none_junk_or_a_disabled_preset(preset):
    assert RE.from_preset(preset) == ""


def _in_fresh_context(fn):
    return contextvars.copy_context().run(fn)


def test_apply_adds_the_kwarg_for_a_local_server():
    def run():
        RE.set_for_preset("custom", {"reasoning_effort": "medium"})
        payload = {"model": "m"}
        RE.apply(payload, self_hosted=True)
        return payload
    assert _in_fresh_context(run)["chat_template_kwargs"] == {"reasoning_effort": "medium"}


def test_apply_leaves_cloud_payloads_and_unset_effort_alone():
    def run():
        RE.set_for_preset("custom", {"reasoning_effort": "medium"})
        cloud = {"model": "m"}
        RE.apply(cloud, self_hosted=False)
        RE.set_for_preset("custom", {})
        local = {"model": "m"}
        RE.apply(local, self_hosted=True)
        return cloud, local
    cloud, local = _in_fresh_context(run)
    assert cloud == {"model": "m"}
    assert local == {"model": "m"}


def test_apply_merges_with_existing_kwargs_and_never_overrides_them():
    def run():
        RE.set_for_preset("custom", {"reasoning_effort": "medium"})
        a = {"chat_template_kwargs": {"enable_thinking": True}}
        b = {"chat_template_kwargs": {"reasoning_effort": "xhigh"}}
        RE.apply(a, True)
        RE.apply(b, True)
        return a, b
    a, b = _in_fresh_context(run)
    assert a["chat_template_kwargs"] == {"enable_thinking": True, "reasoning_effort": "medium"}
    assert b["chat_template_kwargs"] == {"reasoning_effort": "xhigh"}


def test_concurrent_requests_do_not_see_each_others_effort():
    async def request(effort, out):
        RE.set_for_preset("custom", {"reasoning_effort": effort})
        await asyncio.sleep(0.01)
        # A background task started by the request (the detached agent run)
        # inherits the request's value.
        out[effort] = await asyncio.create_task(asyncio.sleep(0, result=RE.current()))

    async def main():
        out = {}
        await asyncio.gather(request("medium", out), request("xhigh", out))
        return out

    assert asyncio.run(main()) == {"medium": "medium", "xhigh": "xhigh"}


# --- through the real request builder (stream_llm) -------------------------------

class _Resp:
    status_code = 200

    async def aiter_lines(self):
        yield 'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}'
        yield "data: [DONE]"

    async def aread(self):
        return b""


class _Ctx:
    async def __aenter__(self):
        return _Resp()

    async def __aexit__(self, *a):
        return False


class _Client:
    def __init__(self, sent):
        self.sent = sent

    def stream(self, method, url, **kw):
        self.sent.append(kw.get("json"))
        return _Ctx()


def _sent_payload(monkeypatch, url, effort):
    sent = []
    monkeypatch.setattr(llm_core, "_get_http_client", lambda: _Client(sent))
    monkeypatch.setattr(llm_core, "_is_host_dead", lambda u: False)
    monkeypatch.setattr(llm_core, "note_model_activity", lambda *a, **k: None)
    monkeypatch.setattr(llm_core, "_clear_host_dead", lambda *a, **k: None)

    async def run():
        RE.set_for_preset("custom", {"reasoning_effort": effort})
        async for _ in llm_core.stream_llm(url, "bonsai2-27b", [{"role": "user", "content": "hi"}]):
            pass

    contextvars.copy_context().run(asyncio.run, run())
    assert sent, "stream_llm sent nothing"
    return sent[0]


def test_stream_llm_sends_the_effort_to_a_local_llama_server(monkeypatch):
    p = _sent_payload(monkeypatch, "http://127.0.0.1:8090/v1/chat/completions", "medium")
    assert p.get("chat_template_kwargs") == {"reasoning_effort": "medium"}


def test_stream_llm_sends_nothing_without_an_effort(monkeypatch):
    p = _sent_payload(monkeypatch, "http://127.0.0.1:8090/v1/chat/completions", "")
    assert "chat_template_kwargs" not in p


def test_stream_llm_never_sends_it_to_a_cloud_api(monkeypatch):
    p = _sent_payload(monkeypatch, "https://api.openai.com/v1/chat/completions", "medium")
    assert "chat_template_kwargs" not in p


def test_a_localhost_v1_server_gets_it_although_upstream_calls_it_ollama(monkeypatch):
    # Upstream's _is_ollama_openai_compat_url is true for any localhost /v1,
    # so Bonsai's llama.cpp on :8090 is "Ollama" to it. A gate on that check
    # would silently drop the effort for the one server it is for.
    assert llm_core._is_ollama_openai_compat_url("http://localhost:8090/v1/chat/completions")
    p = _sent_payload(monkeypatch, "http://localhost:8090/v1/chat/completions", "xhigh")
    assert p.get("chat_template_kwargs") == {"reasoning_effort": "xhigh"}


# --- the preset ------------------------------------------------------------------

def test_preset_update_accepts_known_efforts_and_rejects_others():
    assert PresetUpdateRequest(reasoning_effort="medium").reasoning_effort == "medium"
    assert PresetUpdateRequest().reasoning_effort == ""
    with pytest.raises(ValidationError):
        PresetUpdateRequest(reasoning_effort="extreme")
    with pytest.raises(ValidationError):
        PresetUpdateRequest(reasoning_effort="high")


def test_update_custom_stores_the_effort(tmp_path):
    pm = PresetManager(str(tmp_path))
    assert pm.update_custom(0.6, 8192, "", reasoning_effort="medium")
    reloaded = PresetManager(str(tmp_path))
    assert reloaded.presets["custom"]["reasoning_effort"] == "medium"
    assert RE.from_preset(reloaded.presets["custom"]) == "medium"


def test_extract_preset_sets_the_request_effort_from_the_preset():
    from types import SimpleNamespace
    from routes import chat_helpers

    presets = {"custom": {"reasoning_effort": "medium", "enabled": True}}
    handler = SimpleNamespace(
        preset_manager=SimpleNamespace(presets=presets),
        validate_and_extract_preset=lambda pid: (0.6, 8192, None, ""),
    )

    def run(pid):
        chat_helpers.extract_preset(handler, pid)
        return RE.current()

    assert contextvars.copy_context().run(run, "custom") == "medium"
    # A request without a preset clears it, so nothing carries over.
    assert contextvars.copy_context().run(run, None) == ""
