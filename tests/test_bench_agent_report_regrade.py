"""bench_agent.py report: --split-runs keeps two runs of one target apart, and
--regrade re-runs today's research checks on saved answers.

Found 2026-10-12: a before/after report pooled Bonsai's 10-10 and 10-12 runs
into one column, and the 10-10 Qwen run kept the grade of the towers check
that rejected "368.03 m" (fixed in 191e474), so it showed 7/10 where today's
check gives more. Site 429s ("Rate limit hit") count as environment errors.
"""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def _bench():
    spec = importlib.util.spec_from_file_location("bench_agent_regrade_test", ROOT / "scripts" / "bench_agent.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _bench()

TOWERS_OK = ("The Berlin TV Tower (Fernsehturm) is taller. Berlin TV Tower: 368.03 m "
             "[Wikipedia](https://en.wikipedia.org/wiki/Fernsehturm_Berlin); Eiffel Tower: 330 m "
             "(https://en.wikipedia.org/wiki/Eiffel_Tower). The Berlin TV Tower is 38.03 metres taller.")
TOWERS_WRONG = "The Fernsehturm is 365 m and the Eiffel Tower 300 m; taller by 65 m (https://x.org)."


def _rec(target, text, passed, tool_output="ok", exit_code=0):
    return {"task": "res_towers", "cat": "research", "target": target, "model": "m", "rep": 1,
            "passed": passed, "status": "ok", "flags": [], "final_text": text, "text": text,
            "checks": [{"name": "old check", "ok": passed, "detail": ""}],
            "tools": [{"tool": "web_search"}],
            "tool_results": [{"tool": "web_fetch", "exit_code": exit_code, "output": tool_output}]}


def _run_dir(tmp_path, name, target, recs):
    d = tmp_path / name
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"target": target, "env": {}}))
    (d / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    return str(d)


def _report(tmp_path, dirs, **kw):
    out = tmp_path / "report.md"
    B.cmd_report(SimpleNamespace(dirs=dirs, log=str(tmp_path / "none.log"), out=str(out), **kw))
    return out.read_text()


def test_without_split_two_runs_of_one_target_pool_into_one_column(tmp_path):
    a = _run_dir(tmp_path, "20261010-194252-bonsai2-research", "bonsai2", [_rec("bonsai2", TOWERS_OK, True)])
    b = _run_dir(tmp_path, "20261012-201046-bonsai2-research", "bonsai2", [_rec("bonsai2", TOWERS_OK, True)])
    text = _report(tmp_path, [a, b])
    assert "**bonsai2** (m, 2 task runs)" in text


def test_split_runs_gives_each_run_folder_its_own_column(tmp_path):
    a = _run_dir(tmp_path, "20261010-194252-bonsai2-research", "bonsai2", [_rec("bonsai2", TOWERS_OK, True)])
    b = _run_dir(tmp_path, "20261012-201046-bonsai2-research", "bonsai2", [_rec("bonsai2", TOWERS_WRONG, False)])
    text = _report(tmp_path, [a, b], split_runs=True)
    assert "bonsai2 20261010-1942" in text and "bonsai2 20261012-2010" in text
    assert "| Tasks passed | **1/1**" in text and "**0/1**" in text


def test_regrade_applies_todays_check_to_saved_answers_both_ways(tmp_path, capsys):
    a = _run_dir(tmp_path, "r", "qwen35", [_rec("qwen35", TOWERS_OK, False),     # old check rejected 368.03
                                           _rec("qwen35", TOWERS_WRONG, True)])  # and a wrong pass
    assert "**1/2**" in _report(tmp_path, [a])
    text = _report(tmp_path, [a], regrade=True)
    assert "**1/2**" in text
    assert "res_towers" in text and "365" in text            # the wrong answer is now listed as a failure
    assert "2 changed" in capsys.readouterr().err


def test_regrade_leaves_other_suites_alone(tmp_path):
    rec = {**_rec("q", "anything", True), "task": "arith", "cat": "restraint"}
    a = _run_dir(tmp_path, "r", "q", [rec])
    assert "**1/1**" in _report(tmp_path, [a], regrade=True)


def test_a_site_429_counts_as_an_environment_error(tmp_path):
    rec = _rec("q", TOWERS_OK, True, tool_output="web_fetch: https://shop.example/blogs/x: Rate limit hit for "
                                                 "https://shop.example/blogs/x (attempt 1)", exit_code=1)
    text = _report(tmp_path, [_run_dir(tmp_path, "r", "q", [rec])])
    assert "1 of 1 (1 environment" in text


def test_split_runs_with_no_shared_task_does_not_crash(tmp_path):
    # 2026-10-14: a webhard run and a research run in one --split-runs report
    # share no task, and the "only tasks every model ran" row divided by zero.
    a = _run_dir(tmp_path, "20261014-150000-qwen35lm-webhard", "qwen35lm",
                 [{**_rec("qwen35lm", "x", True), "task": "wh_mercury_day", "cat": "webhard"}])
    b = _run_dir(tmp_path, "20261014-160000-qwen35lm-research", "qwen35lm", [_rec("qwen35lm", TOWERS_OK, True)])
    text = _report(tmp_path, [a, b], split_runs=True)
    assert "| Tasks passed — only tasks every model ran | – | – |" in text
