"""bench_agent.py: tasks are sent the way the browser sends real chats.

- Only file tasks get a workspace. Real web/document chats have none, and the
  workspace path sits in the system prompt, so it also decides whether a task
  can reuse the previous task's cached prompt start.
- A document "open in the panel" is sent as active_doc_id with every request
  of the chat, approval answers included (static/js/chat.js).
- A task can have follow-up messages in the same chat; time and rounds are
  recorded per message.
"""
import importlib.util
import json
import re
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def _bench():
    spec = importlib.util.spec_from_file_location("bench_agent_chat_shape_test", ROOT / "scripts" / "bench_agent.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _bench()
T = B.T


class _Api:
    """A fake Odysseus: documents in memory, one approval card on request."""

    def __init__(self, card_on_first=False):
        self.forms, self.docs, self.card_on_first = [], {}, card_on_first

    def post(self, path, form=None, js=None, **kw):
        if path == "/api/session":
            return {"id": "sess-1"}
        if path == "/api/document":
            doc_id = f"doc-{len(self.docs) + 1}"
            self.docs[doc_id] = dict(js, id=doc_id, current_content=js["content"])
            return dict(self.docs[doc_id])
        return {}

    def get(self, path, params=None):
        if path.startswith("/api/documents/"):
            return list(self.docs.values())
        if path.startswith("/api/document/"):
            return self.docs.get(path.rsplit("/", 1)[1])
        return {}

    def delete(self, path):
        return {}

    def stream(self, path, form, on_line, timeout=None):
        self.forms.append(dict(form))
        msg = form.get("message") or ""
        m = re.search(r'"(\[bench-[0-9a-f]{4}\] Day pack)"', msg)
        if m:   # the model "creates" the document of message 1
            self.post("/api/document", js={"session_id": "sess-1", "title": m.group(1), "content": "- a\n- b\n- c\n"})
        if self.card_on_first and len(self.forms) == 1:
            card = {"kind": "tool_approval", "approval_id": "appr-1", "question": "Allow?"}
            on_line("data: " + json.dumps({"type": "ask_user", "data": card}))
        else:
            on_line("data: " + json.dumps({"delta": "done"}))
        on_line("data: [DONE]")


def _run(tmp_path, monkeypatch, task_id, api):
    monkeypatch.setattr(B, "WS_ROOT", tmp_path / "ws")
    task = next(t for t in T.TASKS if t["id"] == task_id)
    args = SimpleNamespace(task_timeout=600, max_approvals=3, approval="allow_task", preset=None, keep=True)
    run_dir = tmp_path / "run"
    run_dir.mkdir(exist_ok=True)
    return B.run_one(api, task, ("bonsai2", ("ed1cd41c", "bonsai2-27b")), 1, run_dir, args)


def test_file_tasks_get_a_workspace_and_chat_tasks_do_not(tmp_path, monkeypatch):
    api = _Api()
    _run(tmp_path, monkeypatch, "read_fact", api)
    _run(tmp_path, monkeypatch, "web_read", api)
    _run(tmp_path, monkeypatch, "arith", api)
    assert "workspace" in api.forms[0]
    assert "workspace" not in api.forms[1] and "workspace" not in api.forms[2]


def test_every_non_file_task_runs_without_a_workspace():
    file_tools = {"read_file", "write_file", "edit_file", "apply_patch", "bash", "grep", "glob", "ls"}
    for t in T.TASKS:
        assert t["workspace"] == bool(set(t["tools"]) & file_tools), t["id"]


def test_the_open_document_goes_with_the_message_and_the_approval_answer(tmp_path, monkeypatch):
    api = _Api(card_on_first=True)
    rec = _run(tmp_path, monkeypatch, "document_edit", api)
    assert len(api.forms) == 2
    message, answer = api.forms
    assert message["active_doc_id"] == answer["active_doc_id"] == "doc-1"
    assert answer["tool_approval_id"] == "appr-1"
    assert api.docs["doc-1"]["title"].endswith("Grow log")
    assert rec["turns"] and len(rec["turns"]) == 1


def test_a_follow_up_is_a_second_message_in_the_same_chat_with_the_new_document(tmp_path, monkeypatch):
    api = _Api()
    rec = _run(tmp_path, monkeypatch, "document_followup", api)
    assert [f["message"][:6] for f in api.forms] == ["Create", "Add a "]
    assert {f["session"] for f in api.forms} == {"sess-1"}
    assert "active_doc_id" not in api.forms[0]
    assert api.forms[1]["active_doc_id"] == "doc-1"
    assert len(rec["turns"]) == 2 and all("wall_s" in t for t in rec["turns"])


def _edit_ctx(content):
    api = _Api()
    doc = api.post("/api/document", js={"session_id": "s", "title": "[bench-abcd] Grow log", "content": content})
    return {"api": api, "doc_id": doc["id"], "session": "s", "marker": "[bench-abcd]"}


def _results(content):
    return {name: ok for name, ok, _ in T._check_doc_edit({}, _edit_ctx(content))}


def test_doc_edit_passes_only_the_requested_change():
    edited = "\n".join(T.GROW_LOG).replace("80 %", "85 %")
    assert all(_results(edited).values())


def test_doc_edit_fails_when_nothing_changed():
    r = _results("\n".join(T.GROW_LOG))
    assert not r["humidity target is 85 %"] and not r["no 80 % left"]


def test_doc_edit_fails_when_another_line_was_rewritten():
    edited = "\n".join(T.GROW_LOG).replace("80 %", "85 %").replace("straw pellets", "straw")
    r = _results(edited)
    assert r["humidity target is 85 %"] and not r["every other line unchanged"]
