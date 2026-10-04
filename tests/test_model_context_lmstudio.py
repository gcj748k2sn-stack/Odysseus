"""LM Studio's LOADED context window must beat the known-models table.

Observed 2026-10-04 (session 933f8674, "what is the current value of gold in
euro…"): LM Studio had `qwen/qwen3.5-9b` loaded at 32768, but
`_query_context_length` returned the known table's 131072 for "qwen3" —
LM Studio answers `/slots` with a 200 that is not a list, and its
OpenAI-compatible `/v1/models` carries no context field. Nothing was trimmed
against the real window, the turn grew to 39,659 tokens, and LM Studio's
"Truncate Middle" overflow policy removed 22,510 / 25,702 / 27,445 tokens from
the middle of rounds 12-14. The final answer quoted two prices that appear in
no fetched page.

Fix under test: for local endpoints, after `/slots`, read LM Studio's native
`/api/v1/models` (`models[].loaded_instances[].config.context_length`).

⚠️ The payloads below follow LM Studio's documented response shape, with model
keys taken from this machine's `~/.lmstudio/.internal/model-data.json`. They are
NOT a recorded response — the live check is the `LM Studio reports loaded
context` line in app.log (docs/todo.md, "LM Studio's loaded context is invisible
to Odysseus").
"""

import httpx
import pytest

import src.model_context as mc

LMS = "http://localhost:1234/v1"


class _Resp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self.is_success = 200 <= status < 300
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _model(key, contexts=(), *, ids=None, max_ctx=262144, kind="llm"):
    ids = ids or [key] * len(contexts)
    return {
        "type": kind,
        "key": key,
        "display_name": key.split("/")[-1],
        "architecture": "qwen3_5",
        "max_context_length": max_ctx,
        "loaded_instances": [
            {"id": i, "config": {"context_length": c, "parallel": 1}}
            for i, c in zip(ids, contexts)
        ],
    }


def _route(monkeypatch, *, native=None, native_status=200, slots=None, calls=None):
    """Fake httpx.get by URL. Defaults mimic LM Studio 0.4: /slots is answered
    with a 200 that is not a list, /v1/models carries no context field."""
    def _get(url, *a, **k):
        if calls is not None:
            calls.append(url)
        if url.endswith("/slots"):
            return _Resp(200, slots if slots is not None else {"error": "Unexpected endpoint or method. (GET /slots)"})
        if url.endswith("/api/v1/models"):
            if native is None:
                return _Resp(404, {"error": "not found"})
            return _Resp(native_status, native)
        if url.endswith("/models"):
            return _Resp(200, {"object": "list", "data": [{"id": "qwen/qwen3.5-9b", "object": "model"}]})
        raise httpx.ConnectError(f"unexpected URL in test: {url}")
    monkeypatch.setattr(mc.httpx, "get", _get)
    monkeypatch.setattr(mc, "_configured_endpoint_kind", lambda url: None)


def _payload(*models):
    return {"models": list(models)}


# --- the observed case ------------------------------------------------------

def test_loaded_context_beats_known_table(monkeypatch):
    _route(monkeypatch, native=_payload(_model("qwen/qwen3.5-9b", [32768])))
    assert mc._lookup_known("qwen/qwen3.5-9b") == 131072  # what used to be returned
    assert mc._query_context_length(LMS, "qwen/qwen3.5-9b") == (32768, True)


def test_chat_completions_url_probes_the_server_root(monkeypatch):
    calls = []
    _route(monkeypatch, native=_payload(_model("qwen/qwen3.5-9b", [32768])), calls=calls)
    ctx, known = mc._query_context_length("http://localhost:1234/v1/chat/completions", "qwen/qwen3.5-9b")
    assert (ctx, known) == (32768, True)
    assert "http://localhost:1234/api/v1/models" in calls


def test_budget_scales_off_the_loaded_window(monkeypatch):
    _route(monkeypatch, native=_payload(_model("qwen/qwen3.5-9b", [32768])))
    assert mc.budget_context_for_model(LMS, "qwen/qwen3.5-9b") == 32768


def test_reload_at_a_new_size_is_picked_up_without_a_restart(monkeypatch):
    # Local endpoints are never cached, so a reload must show up on the next lookup.
    _route(monkeypatch, native=_payload(_model("qwen/qwen3.5-9b", [32768])))
    assert mc.get_context_length_known(LMS, "qwen/qwen3.5-9b") == (32768, True)
    _route(monkeypatch, native=_payload(_model("qwen/qwen3.5-9b", [16384])))
    assert mc.get_context_length_known(LMS, "qwen/qwen3.5-9b") == (16384, True)


# --- matching ---------------------------------------------------------------

def test_bare_name_matches_key_tail(monkeypatch):
    _route(monkeypatch, native=_payload(_model("qwen/qwen3.5-9b", [32768])))
    assert mc._query_context_length(LMS, "qwen3.5-9b") == (32768, True)


def test_exact_key_beats_a_tail_match_from_another_publisher(monkeypatch):
    _route(monkeypatch, native=_payload(
        _model("other/qwen3.5-9b", [4096]),
        _model("qwen/qwen3.5-9b", [32768]),
    ))
    assert mc._query_context_length(LMS, "qwen/qwen3.5-9b") == (32768, True)


def test_custom_api_identifier_matches_the_instance_and_beats_its_name_suffix(monkeypatch):
    # Loaded with --identifier qwen3.5-9b-32k but actually at 16384: the live
    # report must win over what the name claims.
    _route(monkeypatch, native=_payload(
        _model("qwen/qwen3.5-9b", [16384], ids=["qwen3.5-9b-32k"]),
    ))
    assert mc._query_context_length(LMS, "qwen3.5-9b-32k") == (16384, True)


def test_an_instance_named_exactly_as_requested_wins(monkeypatch):
    # A second copy loads as "<key>:2"; a request for "<key>" goes to the
    # instance whose identifier IS "<key>", so that instance's window applies.
    _route(monkeypatch, native=_payload(
        _model("qwen/qwen3.5-9b", [32768, 8192], ids=["qwen/qwen3.5-9b", "qwen/qwen3.5-9b:2"]),
    ))
    assert mc._query_context_length(LMS, "qwen/qwen3.5-9b") == (32768, True)
    assert mc._query_context_length(LMS, "qwen/qwen3.5-9b:2") == (8192, True)


def test_key_match_without_an_exact_instance_uses_the_smallest_window(monkeypatch):
    # No instance carries the requested name, so the request could land on
    # either — budget for the smaller one.
    _route(monkeypatch, native=_payload(
        _model("qwen/qwen3.5-9b", [32768, 8192], ids=["fast", "slow"]),
    ))
    assert mc._query_context_length(LMS, "qwen/qwen3.5-9b") == (8192, True)


# --- listed but not loaded --------------------------------------------------

def test_listed_but_not_loaded_is_unknown_not_the_table(monkeypatch):
    _route(monkeypatch, native=_payload(_model("qwen/qwen3.5-9b", [])))
    assert mc._query_context_length(LMS, "qwen/qwen3.5-9b") == (mc.DEFAULT_CONTEXT, False)
    # ...so the input budget stays conservative instead of scaling off 131072.
    assert mc.budget_context_for_model(LMS, "qwen/qwen3.5-9b") == 0


# --- negative controls: everything else behaves exactly as before ------------

def test_not_lmstudio_falls_through_to_name_suffix(monkeypatch):
    # Ollama: /slots and /api/v1/models both 404 → the "-64k" suffix still decides.
    def _get(url, *a, **k):
        return _Resp(404, {"error": "not found"})
    monkeypatch.setattr(mc.httpx, "get", _get)
    monkeypatch.setattr(mc, "_configured_endpoint_kind", lambda url: None)
    assert mc._query_context_length("http://localhost:11434/v1", "qwen3.5:9b-64k") == (65536, True)


def test_not_lmstudio_falls_through_to_known_table(monkeypatch):
    def _get(url, *a, **k):
        raise httpx.ConnectError("refused")
    monkeypatch.setattr(mc.httpx, "get", _get)
    monkeypatch.setattr(mc, "_configured_endpoint_kind", lambda url: None)
    assert mc._query_context_length("http://localhost:11434/v1", "qwen3.5:9b") == (
        mc._lookup_known("qwen3.5:9b"), True)


def test_model_not_listed_falls_through(monkeypatch):
    _route(monkeypatch, native=_payload(_model("prism-ml/ternary-bonsai-2-27b-mlx-2bit", [32768])))
    assert mc._query_context_length(LMS, "qwen/qwen3.5-9b") == (131072, True)


@pytest.mark.parametrize("native", [
    {"data": [{"id": "qwen/qwen3.5-9b"}]},          # OpenAI shape, not LM Studio's
    {"models": "nope"},
    {"models": [None, 7, "x"]},
    [],
    {"models": [_model("qwen/qwen3.5-9b")]},          # listed, but drop the loaded field entirely
])
def test_malformed_or_foreign_payloads_never_raise(monkeypatch, native):
    if isinstance(native, dict) and isinstance(native.get("models"), list) and native["models"] \
            and isinstance(native["models"][0], dict):
        native["models"][0].pop("loaded_instances", None)
    _route(monkeypatch, native=native)
    ctx, known = mc._query_context_length(LMS, "qwen/qwen3.5-9b")
    assert ctx in (131072, mc.DEFAULT_CONTEXT)


@pytest.mark.parametrize("bad", [True, "32768", 0, -1, None, 3.2e4])
def test_non_integer_contexts_are_ignored(monkeypatch, bad):
    m = _model("qwen/qwen3.5-9b", [32768])
    m["loaded_instances"][0]["config"]["context_length"] = bad
    _route(monkeypatch, native=_payload(m))
    # The only instance has no usable value → treated as not loaded.
    assert mc._query_context_length(LMS, "qwen/qwen3.5-9b") == (mc.DEFAULT_CONTEXT, False)


def test_unparseable_body_falls_through(monkeypatch):
    _route(monkeypatch, native=ValueError("not json"))
    assert mc._query_context_length(LMS, "qwen/qwen3.5-9b") == (131072, True)


def test_llamacpp_slots_still_win(monkeypatch):
    calls = []
    _route(monkeypatch, slots=[{"n_ctx": 8192}],
           native=_payload(_model("qwen/qwen3.5-9b", [32768])), calls=calls)
    assert mc._query_context_length(LMS, "qwen/qwen3.5-9b") == (8192, True)
    assert not any(u.endswith("/api/v1/models") for u in calls)


def test_remote_endpoint_is_never_probed(monkeypatch):
    calls = []
    _route(monkeypatch, native=_payload(_model("qwen/qwen3.5-9b", [32768])), calls=calls)
    monkeypatch.setattr(mc, "is_local_endpoint", lambda url: False)
    mc._query_context_length("https://api.example.com/v1", "qwen/qwen3.5-9b")
    assert not any(u.endswith("/api/v1/models") for u in calls)
