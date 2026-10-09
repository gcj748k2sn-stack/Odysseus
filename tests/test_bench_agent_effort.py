"""bench_agent.py: each run records the llama-server's reasoning effort.

Bonsai 2's effort is a server flag (start_bonsai2.sh, --chat-template-kwargs),
so nothing in a run showed which effort it ran at, and a `low` run would have
pooled with the `medium` ones under the name `bonsai2`. Preflight now reads
the server's command line from `ps`, the run is named `bonsai2@<effort>`, and
the report labels older runs from their meta.json.
"""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def _bench():
    spec = importlib.util.spec_from_file_location("bench_agent_effort_test", ROOT / "scripts" / "bench_agent.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _bench()

# What `ps -axww -o command=` prints for start_bonsai2.sh: shell quotes are gone.
BONSAI = ("/Users/x/BonsaiDemo/bin/llama-server -m models/b.gguf --host 127.0.0.1 --port 8090 -ngl 99 "
          "--alias bonsai2-27b -np 1 --reasoning-budget 16384 --ctx-checkpoints 32 "
          "--chat-template-kwargs {\"reasoning_effort\":\"medium\"}")


def test_effort_and_budget_are_read_from_the_command_line():
    f = B.reasoning_flags(BONSAI)
    assert f["reasoning_effort"] == "medium"
    assert f["reasoning_budget"] == 16384


def test_the_last_repeated_flag_wins_like_llama_cpp():
    # start_bonsai2.sh's documented override: pass the flag again at the end.
    f = B.reasoning_flags(BONSAI + " --chat-template-kwargs {\"reasoning_effort\": \"low\"}")
    assert f["reasoning_effort"] == "low"


def test_no_flag_means_the_template_default():
    f = B.reasoning_flags("llama-server -m m.gguf --port 8090")
    assert f["reasoning_effort"] == "default"
    assert f["reasoning_budget"] is None


def test_kwargs_without_effort_are_not_mistaken_for_one():
    f = B.reasoning_flags("llama-server --port 8090 --chat-template-kwargs {\"enable_thinking\":true}")
    assert f["reasoning_effort"] == "default"


def test_the_server_on_the_right_port_is_picked(monkeypatch):
    ps = "\n".join([
        "/bin/zsh -l",
        "llama-server -m other.gguf --port 8091 --chat-template-kwargs {\"reasoning_effort\":\"xhigh\"}",
        BONSAI,
        "grep llama-server",
    ])
    monkeypatch.setattr(B.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=ps))
    assert B.llama_server_cmdline(8090) == BONSAI
    assert "8091" in B.llama_server_cmdline(8091)
    assert B.llama_server_cmdline(8092) is None


def _run_dir(tmp_path, name, target, effort):
    d = tmp_path / name
    d.mkdir()
    lc = {"model_path": "m.gguf"}
    if effort:
        lc["reasoning_effort"] = effort
    (d / "meta.json").write_text(json.dumps({"target": target, "env": {"llamacpp": lc}}))
    rec = {"task": "arith", "cat": "restraint", "target": target, "model": "bonsai2-27b", "rep": 1,
           "passed": True, "checks": [], "tools": [], "flags": [], "status": "ok"}
    (d / "results.jsonl").write_text(json.dumps(rec) + "\n")
    return str(d)


def test_report_keeps_efforts_apart_and_labels_old_runs(tmp_path):
    old = _run_dir(tmp_path, "a", "bonsai2", "medium")           # pre-change name, backfilled meta
    new = _run_dir(tmp_path, "b", "bonsai2@low", "low")          # named at run time
    unknown = _run_dir(tmp_path, "c", "qwen35", None)            # LM Studio: no effort
    out = tmp_path / "report.md"
    B.cmd_report(SimpleNamespace(dirs=[old, new, unknown], log=str(tmp_path / "none.log"), out=str(out)))
    text = out.read_text()
    assert "bonsai2@medium" in text and "bonsai2@low" in text and "qwen35" in text
    assert "**bonsai2**" not in text
