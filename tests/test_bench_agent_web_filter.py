"""bench_agent.py run --web-filter on|off: an A/B of Odysseus's web relevance
filter. The run switches the admin setting, is named TARGET-filteron/-filteroff
so the two arms never pool, records the setting in meta.json, and restores the
previous value on exit (it changes the user's live configuration).
"""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _bench():
    spec = importlib.util.spec_from_file_location("bench_agent_web_filter_test", ROOT / "scripts" / "bench_agent.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _bench()


def _setup(monkeypatch, tmp_path, enabled=True, sticky=False):
    state = {"web_filter_enabled": enabled, "puts": []}
    exits = []

    class Api:
        def __init__(self, *a):
            pass

        def login(self):
            pass

        def get(self, path, params=None):
            assert path == "/api/web-filter/settings"
            return {"web_filter_enabled": state["web_filter_enabled"]}

        def put(self, path, js=None):
            state["puts"].append(js)
            if not sticky:
                state.update(js)
            return {"web_filter_enabled": state["web_filter_enabled"]}

    monkeypatch.setattr(B, "Api", Api)
    monkeypatch.setattr(B.time, "sleep", lambda s: None)
    monkeypatch.setattr(B.atexit, "register", lambda fn, *a: exits.append((fn, a)))
    monkeypatch.setattr(B, "preflight", lambda api, target, tasks: ({"skipped": {}}, []))
    monkeypatch.setattr(B, "run_one", lambda api, task, target, rep, rd, args: {
        "task": task["id"], "cat": task["cat"], "target": target[0], "model": "m", "rep": rep, "status": "ok",
        "passed": True, "checks": [], "tools": [], "flags": []})
    monkeypatch.setattr(B, "RESULTS_ROOT", tmp_path)
    return state, exits


def _args(**kw):
    return SimpleNamespace(**{"target": "qwen35lm", "quick": False, "tasks": "res_esp32c3", "runs": 1,
                              "resume": None, "preset": None, "no_warmup": True, "yes": True,
                              "url": "http://x", "user": "u", "suite": "research", **kw})


def test_filter_off_run_is_named_apart_records_the_setting_and_restores_it(monkeypatch, tmp_path):
    state, exits = _setup(monkeypatch, tmp_path, enabled=True)
    B.cmd_run(_args(web_filter="off"))
    meta = json.loads(next(tmp_path.glob("*/meta.json")).read_text())
    assert meta["target"] == "qwen35lm-filteroff"
    assert meta["env"]["web_filter"] == {"web_filter_enabled": False}
    assert state["puts"] == [{"web_filter_enabled": False}]
    assert len(exits) == 1
    fn, a = exits[0]
    fn(*a)
    assert state["web_filter_enabled"] is True


def test_asking_for_the_current_state_changes_nothing_on_exit(monkeypatch, tmp_path):
    state, exits = _setup(monkeypatch, tmp_path, enabled=True)
    B.cmd_run(_args(web_filter="on"))
    assert json.loads(next(tmp_path.glob("*/meta.json")).read_text())["target"] == "qwen35lm-filteron"
    assert exits == []


def test_a_setting_that_does_not_take_stops_the_run(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, enabled=True, sticky=True)
    with pytest.raises(SystemExit, match="still on"):
        B.cmd_run(_args(web_filter="off"))
    assert not list(tmp_path.glob("*/meta.json"))


def test_without_the_flag_nothing_is_switched_but_the_state_is_recorded(monkeypatch, tmp_path):
    state, exits = _setup(monkeypatch, tmp_path, enabled=False)
    B.cmd_run(_args())
    meta = json.loads(next(tmp_path.glob("*/meta.json")).read_text())
    assert meta["target"] == "qwen35lm" and meta["env"]["web_filter"] == {"web_filter_enabled": False}
    assert state["puts"] == [] and exits == []
