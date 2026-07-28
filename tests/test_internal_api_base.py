"""internal_api_base() resolution + a guard that loopback call sites use it."""
import importlib
import pathlib

import pytest

import core.constants as cc


import src.constants as sc


def _base(monkeypatch, **env):
    for k in ("ODYSSEUS_INTERNAL_BASE", "APP_PORT"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(sc, "_runtime_bind_port", None)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return cc.internal_api_base()


def test_default_is_legacy_7000(monkeypatch):
    assert _base(monkeypatch) == "http://127.0.0.1:7000"


def test_app_port_is_honored(monkeypatch):
    assert _base(monkeypatch, APP_PORT="7860") == "http://127.0.0.1:7860"


def test_explicit_override_wins_and_is_stripped(monkeypatch):
    # Override beats APP_PORT and trailing slash is trimmed.
    assert _base(monkeypatch, APP_PORT="7860",
                 ODYSSEUS_INTERNAL_BASE="https://proxy.example/") == "https://proxy.example"


def test_uses_127_not_localhost(monkeypatch):
    # 127.0.0.1 avoids IPv6/DNS ambiguity for the strictly-local loopback.
    assert "localhost" not in _base(monkeypatch)


def test_runtime_bind_port_beats_app_port_and_fallback(monkeypatch):
    # The port the server is actually bound to (observed from the ASGI scope)
    # beats the APP_PORT guess and the legacy 7000 fallback — 7000 is macOS
    # AirPlay Receiver, which answers 403 to loopback tool calls.
    _base(monkeypatch, APP_PORT="7860")  # clears env + runtime port
    sc.set_runtime_bind_port(8123)
    assert cc.internal_api_base() == "http://127.0.0.1:8123"


def test_explicit_override_beats_runtime_bind_port(monkeypatch):
    _base(monkeypatch, ODYSSEUS_INTERNAL_BASE="https://proxy.example")
    sc.set_runtime_bind_port(8123)
    assert cc.internal_api_base() == "https://proxy.example"


def test_runtime_bind_port_rebinds_frozen_tool_base(monkeypatch):
    # src/tools/_common.py freezes _INTERNAL_BASE at import; the setter must
    # refresh it (tool call sites import it function-locally at call time).
    import src.tools._common as common
    import src.tool_implementations as facade
    _base(monkeypatch)
    monkeypatch.setattr(common, "_INTERNAL_BASE", "http://127.0.0.1:7000")
    monkeypatch.setattr(facade, "_INTERNAL_BASE", "http://127.0.0.1:7000")
    sc.set_runtime_bind_port(8123)
    assert common._INTERNAL_BASE == "http://127.0.0.1:8123"
    assert facade._INTERNAL_BASE == "http://127.0.0.1:8123"


def test_record_bound_port_reads_asgi_server_scope(monkeypatch):
    from core import middleware as mw
    _base(monkeypatch)
    monkeypatch.setattr(mw, "_bound_port_recorded", False)

    class _Req:
        scope = {"server": ("127.0.0.1", 8123)}

    mw._record_bound_port(_Req())
    assert cc.internal_api_base() == "http://127.0.0.1:8123"
    # One-shot: later requests don't re-record.
    assert mw._bound_port_recorded is True


def test_no_hardcoded_loopback_left_in_call_sites():
    # Regression guard: the converted files must not reintroduce the literal.
    root = pathlib.Path(__file__).resolve().parent.parent
    for rel in (
        "src/tools/_common.py",
        "src/cookbook_serve_lifecycle.py",
        "src/builtin_actions.py",
        "routes/task_routes.py",
    ):
        text = (root / rel).read_text(encoding="utf-8")
        # Allow it only inside comments; flag any code occurrence.
        for ln in text.splitlines():
            stripped = ln.strip()
            if stripped.startswith("#"):
                continue
            assert "localhost:7000" not in ln, f"{rel}: hardcoded loopback URL: {ln.strip()}"
