"""bench_agent.py: tasks whose tools are switched off are skipped, not failed.

calendar_create needs manage_calendar; with that tool switched off in
Settings → Agent Tools it could only fail, which would count against the
model. The run skips it and the report lists it as ⏭ instead.
"""
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def _bench():
    spec = importlib.util.spec_from_file_location("bench_agent_under_test", ROOT / "scripts" / "bench_agent.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _bench()
T = B.T


def test_a_task_whose_only_tool_is_off_is_skipped():
    out = B.unrunnable(T.TASKS, ["manage_calendar", "send_email"])
    assert out == {"calendar_create": ["manage_calendar"]}


def test_a_task_with_an_alternative_tool_still_runs():
    # find_file can use grep, glob, bash, ls or read_file
    assert "find_file" not in B.unrunnable(T.TASKS, ["grep", "glob", "bash", "ls"])
    assert "find_file" in B.unrunnable(T.TASKS, ["grep", "glob", "bash", "ls", "read_file"])


def test_tasks_that_need_no_tool_are_never_skipped():
    every_tool = {x for t in T.TASKS for x in t["tools"]}
    out = B.unrunnable(T.TASKS, every_tool)
    assert "arith" in {t["id"] for t in T.TASKS if not t["tools"]}
    assert "arith" not in out and "explain" not in out


def test_nothing_is_skipped_when_the_list_could_not_be_read():
    assert B.unrunnable(T.TASKS, None) == {}


def test_disabled_tools_reads_the_agent_tools_endpoint():
    class Api:
        def get(self, path):
            assert path == "/api/tools"
            return {"tools": [{"id": "manage_calendar", "enabled": False},
                              {"id": "read_file", "enabled": True},
                              {"id": "manage_skills", "enabled": False}]}
    assert B.disabled_tools(Api()) == ["manage_calendar", "manage_skills"]


def _rec(task, target="bonsai2", passed=True):
    t = next(x for x in T.TASKS if x["id"] == task)
    return {"task": task, "cat": t["cat"], "target": target, "model": "m", "rep": 1, "passed": passed,
            "status": "ok", "checks": [], "tools": [], "flags": [], "wall_s": 10}


def _report(tmp_path, runs):
    dirs = []
    for i, (meta, recs) in enumerate(runs):
        d = tmp_path / f"run{i}"
        d.mkdir()
        (d / "meta.json").write_text(json.dumps(meta))
        (d / "results.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
        dirs.append(str(d))
    out = tmp_path / "report.md"
    B.cmd_report(SimpleNamespace(dirs=dirs, log=str(tmp_path / "no-log*"), out=str(out)))
    return out.read_text()


def test_report_marks_the_skipped_task_and_explains_it(tmp_path, capsys):
    meta = {"target": "bonsai2", "env": {"skipped": {"calendar_create": ["manage_calendar"]}}}
    text = _report(tmp_path, [(meta, [_rec("arith"), _rec("note_create")])])
    row = next(l for l in text.splitlines() if l.startswith("| calendar_create |"))
    assert "⏭ tool off" in row
    assert "skipped, tool switched off: calendar_create (manage_calendar)" in text
    assert "it is in no pass rate" in text
    assert "**2/2**" in text   # the skipped task is not a failure


def test_a_task_run_in_another_run_of_the_target_is_not_shown_as_skipped(tmp_path, capsys):
    skipped = {"target": "bonsai2", "env": {"skipped": {"calendar_create": ["manage_calendar"]}}}
    ran = {"target": "bonsai2", "env": {}}
    text = _report(tmp_path, [(skipped, [_rec("arith")]), (ran, [_rec("calendar_create")])])
    row = next(l for l in text.splitlines() if l.startswith("| calendar_create |"))
    assert "⏭" not in row and "1/1" in row
    assert "it is in no pass rate" not in text   # nothing is skipped across the target's runs


def test_run_never_starts_a_skipped_task(tmp_path, monkeypatch, capsys):
    started = []

    class Api:
        def __init__(self, *a):
            pass

        def login(self):
            pass

    def fake_preflight(api, target, tasks):
        return {"skipped": B.unrunnable(tasks, ["manage_calendar"])}, []

    def fake_run_one(api, task, target, rep, run_dir, args):
        started.append(task["id"])
        return _rec(task["id"])

    monkeypatch.setattr(B, "Api", Api)
    monkeypatch.setattr(B, "preflight", fake_preflight)
    monkeypatch.setattr(B, "run_one", fake_run_one)
    monkeypatch.setattr(B, "RESULTS_ROOT", tmp_path)
    args = SimpleNamespace(target="bonsai2", quick=False, tasks="arith,calendar_create", runs=1, resume=None,
                           preset=None, no_warmup=True, yes=True, url="http://x", user="u")
    B.cmd_run(args)
    assert started == ["arith"]
    meta = json.loads(next(tmp_path.glob("*/meta.json")).read_text())
    assert meta["tasks"] == ["arith"]
    assert meta["env"]["skipped"] == {"calendar_create": ["manage_calendar"]}
