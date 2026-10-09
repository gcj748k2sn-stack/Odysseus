"""bench_agent.py: an approval answer carries the message's tool toggles.

The browser builds the approval answer in the same FormData as a message, so
allow_bash / allow_web_search go with it (static/js/chat.js). The benchmark
sent the answer without them; the server reads a missing allow_bash as "not
restricted", added bash to the tool list and re-read the whole prompt on every
approved task. Measured cost in notes/benchmark.md (Bonsai full run, 2026-10-09).
"""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def _bench():
    spec = importlib.util.spec_from_file_location("bench_agent_approval_test", ROOT / "scripts" / "bench_agent.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _bench()
T = B.T


class _Api:
    """Answers the first chat_stream with an approval card, the second with an answer."""

    def __init__(self):
        self.forms = []

    def post(self, path, form=None, **kw):
        return {"id": "sess-1"}

    def get(self, path, **kw):
        return {}

    def stream(self, path, form, on_line, timeout=None):
        self.forms.append(dict(form))
        if len(self.forms) == 1:
            card = {"kind": "tool_approval", "approval_id": "appr-1", "question": "Allow this task to continue?"}
            on_line("data: " + json.dumps({"type": "ask_user", "data": card}))
        else:
            on_line("data: " + json.dumps({"delta": "36"}))
        on_line("data: [DONE]")


def _run(tmp_path, monkeypatch, task_id, preset=None):
    monkeypatch.setattr(B, "WS_ROOT", tmp_path / "ws")
    task = next(t for t in T.TASKS if t["id"] == task_id)
    api = _Api()
    args = SimpleNamespace(task_timeout=600, max_approvals=3, approval="allow_task", preset=preset, keep=True)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    B.run_one(api, task, ("bonsai2", ("ed1cd41c", "bonsai2-27b")), 1, run_dir, args)
    return api.forms


def test_the_approval_answer_keeps_the_messages_bash_and_web_toggles(tmp_path, monkeypatch):
    forms = _run(tmp_path, monkeypatch, "read_fact")
    assert len(forms) == 2, "the approval card was not answered"
    first, answer = forms
    assert answer["tool_approval_id"] == "appr-1"
    assert first["allow_bash"] == "false"
    assert answer["allow_bash"] == first["allow_bash"]
    assert answer["allow_web_search"] == first["allow_web_search"]


def test_a_bash_task_keeps_bash_allowed_on_the_answer(tmp_path, monkeypatch):
    forms = _run(tmp_path, monkeypatch, "shell_count", preset="custom")
    first, answer = forms
    assert first["allow_bash"] == answer["allow_bash"] == "true"
    assert answer["preset_id"] == "custom"
