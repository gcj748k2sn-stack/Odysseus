"""trigger_research must not report "started" for a run whose model is down.

Seen 2026-10-04 20:00:12, session cdb89980: the tool returned *"Deep research
started"* (exit_code 0) and 8 ms later the background task logged
``Probe failed for qwen/qwen3.5-9b: 503: Cannot reach http://localhost:1234``.
The probe ran inside the background task, after the HTTP route had already
answered, so the agent planned around a run that never existed (notes/todo.md,
*"trigger_research reports success when the research model is down"*).

Now the tool asks ``/api/research/start`` to wait for the probe
(``wait_for_probe``), the route waits on ``ResearchHandler.wait_until_started``,
and the tool turns a failed probe into an error the agent can act on. The
research panel does not send the flag, so its response is unchanged.
"""
import asyncio
import sys
import types
from types import SimpleNamespace

import pytest

from src.research_handler import ResearchHandler, _format_probe_failure

_DOWN = _format_probe_failure("qwen/qwen3.5-9b", RuntimeError("503: Cannot reach http://localhost:1234"))


def _bare_handler():
    # Skip __init__: it creates data/deep_research and loads the legacy engine.
    h = ResearchHandler.__new__(ResearchHandler)
    h._legacy_engine = None
    h._active_tasks = {}
    return h


def _start(h, sid="rp-0123456789ab"):
    h.start_research(
        session_id=sid, query="oyster mushrooms", llm_endpoint="http://localhost:1234/v1",
        llm_model="qwen/qwen3.5-9b", hard_timeout=60,
    )
    return sid


async def _cancel(h, sid):
    task = h._active_tasks[sid]["task"]
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


# ── ResearchHandler.wait_until_started ──

async def test_wait_reports_a_failed_probe_with_its_reason(monkeypatch):
    async def _probe(endpoint, model, headers=None):
        raise RuntimeError(_DOWN)

    monkeypatch.setattr(ResearchHandler, "_probe_endpoint", staticmethod(_probe))
    h = _bare_handler()
    sid = _start(h)

    out = await h.wait_until_started(sid, timeout=5)

    assert out["state"] == "failed"
    assert "Cannot reach model 'qwen/qwen3.5-9b'" in out["error"]
    assert "localhost:1234" in out["error"]


async def test_wait_reports_started_once_the_probe_passes(monkeypatch):
    """Negative control: a healthy model must read as started, promptly —
    the flag is set by the real call_research_service right after the probe."""
    async def _probe(endpoint, model, headers=None):
        return None

    blocked = asyncio.Event()

    class _Researcher:
        def __init__(self, **kwargs):
            self.findings = []
            self.evolving_report = ""

        async def research(self, *args, **kwargs):
            await blocked.wait()  # never set: the run stays "running"

    fake = types.ModuleType("src.deep_research")
    fake.DeepResearcher = _Researcher
    monkeypatch.setitem(sys.modules, "src.deep_research", fake)
    monkeypatch.setattr("src.settings.get_setting", lambda key, default=None: default)
    monkeypatch.setattr(ResearchHandler, "_probe_endpoint", staticmethod(_probe))
    h = _bare_handler()
    sid = _start(h)

    out = await asyncio.wait_for(h.wait_until_started(sid, timeout=5), timeout=2)

    assert out == {"state": "started"}
    assert h._active_tasks[sid]["status"] == "running"
    await _cancel(h, sid)


async def test_wait_gives_up_as_pending_while_the_probe_is_still_running(monkeypatch):
    gate = asyncio.Event()

    async def _probe(endpoint, model, headers=None):
        await gate.wait()

    monkeypatch.setattr(ResearchHandler, "_probe_endpoint", staticmethod(_probe))
    h = _bare_handler()
    sid = _start(h)

    out = await h.wait_until_started(sid, timeout=0.2)

    assert out == {"state": "pending"}
    await _cancel(h, sid)


# ── POST /api/research/start ──

class _FakeHandler:
    def __init__(self, outcome):
        self._active_tasks = {}
        self.outcome = outcome
        self.waited = []

    def start_research(self, **kwargs):
        self._active_tasks[kwargs["session_id"]] = {"owner": kwargs.get("owner", "")}
        return {"session_id": kwargs["session_id"], "status": "running"}

    async def wait_until_started(self, session_id, timeout=20.0):
        self.waited.append(session_id)
        return self.outcome


def _start_route(monkeypatch, handler):
    import routes.research_routes as rr

    monkeypatch.setattr("src.auth_helpers.require_privilege", lambda request, priv: "alice")
    monkeypatch.setattr(rr, "resolve_endpoint", lambda role, owner=None: ("http://localhost:1234/v1", "qwen/qwen3.5-9b", {}))
    router = rr.setup_research_routes(handler)
    for route in router.routes:
        if getattr(route, "path", "") == "/api/research/start":
            return route.endpoint
    raise AssertionError("POST /api/research/start not registered")


def _body(endpoint, **kw):
    # The request model is local to setup_research_routes; build it from the
    # endpoint's signature so the test uses the real field defaults.
    import inspect

    cls = inspect.signature(endpoint).parameters["body"].annotation
    return cls(query="oyster mushrooms", **kw)


async def test_route_with_wait_for_probe_returns_the_probe_failure(monkeypatch):
    handler = _FakeHandler({"state": "failed", "error": _DOWN})
    endpoint = _start_route(monkeypatch, handler)

    out = await endpoint(body=_body(endpoint, wait_for_probe=True), request=SimpleNamespace(headers={}))

    assert out["status"] == "error"
    assert out["probe"] == "failed"
    assert out["error"] == _DOWN
    assert handler.waited == [out["session_id"]]


async def test_route_without_the_flag_is_unchanged(monkeypatch):
    """The research panel never sends wait_for_probe: same shape, no wait."""
    handler = _FakeHandler({"state": "failed", "error": _DOWN})
    endpoint = _start_route(monkeypatch, handler)

    out = await endpoint(body=_body(endpoint), request=SimpleNamespace(headers={}))

    assert set(out) == {"session_id", "status", "query"}
    assert out["status"] == "running"
    assert handler.waited == []


# ── the trigger_research tool ──

class _Resp:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code
        self.text = str(data)

    def json(self):
        return self._data


def _fake_client(data, sent):
    class _Client:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json=None, headers=None):
            sent.append(json)
            return _Resp(data)

    return _Client


async def _trigger(monkeypatch, data):
    import httpx
    from src.tools.research import do_trigger_research

    sent = []
    monkeypatch.setattr(httpx, "AsyncClient", _fake_client(data, sent))
    out = await do_trigger_research('{"topic": "oyster mushrooms"}', owner="alice")
    return out, sent


async def test_tool_reports_a_dead_research_model_as_an_error(monkeypatch):
    out, sent = await _trigger(monkeypatch, {
        "session_id": "rp-0123456789ab", "status": "error", "probe": "failed", "error": _DOWN,
    })

    assert sent and sent[0]["wait_for_probe"] is True
    assert out["exit_code"] == 1
    assert "did NOT start" in out["error"]
    assert "localhost:1234" in out["error"]
    assert "output" not in out and "ui_event" not in out


async def test_tool_still_reports_a_healthy_start(monkeypatch):
    out, sent = await _trigger(monkeypatch, {
        "session_id": "rp-0123456789ab", "status": "running", "probe": "started",
    })

    assert out["exit_code"] == 0
    assert out["output"].startswith("Deep research started: [oyster mushrooms](#research-rp-0123456789ab)")
    assert "model check" not in out["output"]
    assert out["ui_event"] == "research_started"


async def test_tool_says_so_when_the_check_has_not_finished(monkeypatch):
    out, _ = await _trigger(monkeypatch, {
        "session_id": "rp-0123456789ab", "status": "running", "probe": "pending",
    })

    assert out["exit_code"] == 0
    assert "model check had not finished" in out["output"]
