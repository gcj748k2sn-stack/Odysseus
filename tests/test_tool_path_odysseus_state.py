"""File tools must not read or write Odysseus's own state (notes/todo.md item 60).

Seen 2026-10-05 08:32/08:34 (session 726f7e32, Bonsai 2): looking for "the
last saved data", the model called read_file on data/app.db twice; the second
read pushed the next request to 36,656 tokens against a 32,768 window. DATA_DIR
was the DEFAULT root for read_file/write_file and the deny-list only knew
home-directory secrets, so the same call could have read data/.app_key (the key
that decrypts stored email passwords and tokens), sessions.json (login tokens)
or settings.json (search API keys) — and write_file could overwrite them.

Merged with upstream 2026-10-06. Upstream fixed the same hole on 2026-09-05
(security advisory, ``_is_app_state_path`` in src/tool_execution.py) with a
containment rule instead of this fork's filename list: everything under
DATA_DIR is refused except the agent-readable subdirectories (agent_workspace,
uploads, mail attachments, personal docs). The fork's list was retired in
favour of it. These tests keep this item's live cases and negative controls,
re-pointed at the merged policy; upstream's own coverage is
tests/test_agent_state_dir_confinement.py.

⚠️ Deliberate tightening, recorded by NOW_REFUSED below: files the fork left
readable directly in data/ (presets.json, memory.json, logs/, skills/, hwfit/)
are refused now too.
"""
import asyncio
import importlib
import os
import shutil
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

STATE = [
    ".app_key", ".key", "auth.json", "sessions.json", "settings.json",
    "cookbook_state.json", "user_prefs.json",
    "app.db", "app.db-journal", "app.db-wal", "app.db-shm", "app.db.bak-before-bonsai2",
    "scheduled_emails.db", "chroma/chroma.sqlite3",
    "settings.json.bak", "auth.json.tmp-123", ".app_key~",
]
ALLOWED = [
    "uploads/report.txt", "uploads/settings.json", "personal_docs/a.md",
    "agent_workspace/notes.md",
]
# Readable under the fork's filename list, refused under upstream's containment.
NOW_REFUSED = [
    "presets.json", "memory.json", "logs/app.log", "skills/notes.md",
    "hwfit/models.json",
]


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """A complete DATA_DIR tree under tmp_path, wired the way
    test_agent_state_dir_confinement.py wires it: the readable subdirectories
    are their own constants, so patching DATA_DIR alone is not enough."""
    data = tmp_path / "data"
    constants = importlib.import_module("src.constants")
    execution = importlib.import_module("src.tool_execution")
    monkeypatch.setattr(constants, "DATA_DIR", str(data), raising=False)
    readable = {
        "AGENT_WORKSPACE_DIR": data / "agent_workspace",
        "UPLOAD_DIR": data / "uploads",
        "MAIL_ATTACHMENTS_DIR": data / "mail-attachments",
        "PERSONAL_DIR": data / "personal_docs",
        "PERSONAL_UPLOADS_DIR": data / "personal_uploads",
    }
    for name, path in readable.items():
        path.mkdir(parents=True)
        monkeypatch.setattr(constants, name, str(path), raising=False)
    monkeypatch.setattr(execution, "AGENT_WORKSPACE_DIR", str(readable["AGENT_WORKSPACE_DIR"]))
    (data / "chroma").mkdir()
    with patch("src.settings.get_setting", return_value=[]):
        yield data


def _execution():
    return importlib.import_module("src.tool_execution")


def _run(tool, content):
    return asyncio.run(_execution()._direct_fallback(tool, content))


# ── the resolver every file tool goes through ──

@pytest.mark.parametrize("rel", STATE)
def test_state_files_are_refused(data_dir, rel):
    with pytest.raises(ValueError, match="application state"):
        _execution()._resolve_tool_path(str(data_dir / rel))


@pytest.mark.parametrize("rel", ALLOWED)
def test_user_content_still_resolves(data_dir, rel):
    """Negative control: the agent-readable subdirectories stay readable —
    including an upload that happens to be called settings.json."""
    target = data_dir / rel
    assert _execution()._resolve_tool_path(str(target)) == os.path.realpath(str(target))


@pytest.mark.parametrize("rel", NOW_REFUSED)
def test_rest_of_data_dir_is_refused_after_the_merge(data_dir, rel):
    with pytest.raises(ValueError, match="application state"):
        _execution()._resolve_tool_path(str(data_dir / rel))


def test_the_same_names_outside_data_dir_are_not_state(data_dir, tmp_path):
    for rel in ("app.db", "settings.json", ".app_key"):
        p = os.path.realpath(str(tmp_path / "elsewhere" / rel))
        assert not _execution()._is_app_state_path(p)


def test_refusal_names_the_tools_that_do_reach_this_data(data_dir):
    """A small model told only "refused" retries the same call; naming the
    right tool is what the 2026-10-05 live check asked for."""
    with pytest.raises(ValueError, match="manage_documents"):
        _execution()._resolve_tool_path(str(data_dir / "app.db"))


def test_workspace_mode_refuses_state_too(data_dir, tmp_path):
    """A workspace that contains data/ (e.g. the repo itself) is a second way in."""
    execution = _execution()
    token = execution._active_workspace.set(str(tmp_path))
    try:
        with pytest.raises(ValueError, match="application state"):
            execution._resolve_tool_path("data/auth.json")
        assert execution._resolve_tool_path("data/uploads/x.txt") == os.path.realpath(
            str(data_dir / "uploads" / "x.txt")
        )
    finally:
        execution._active_workspace.reset(token)


# ── the tools ──

def test_read_file_refuses_the_encryption_key(data_dir):
    (data_dir / ".app_key").write_text("SECRET-KEY-MATERIAL", encoding="utf-8")
    r = _run("read_file", str(data_dir / ".app_key"))
    assert r.get("exit_code") == 1
    assert "manage_documents" in (r.get("error") or "")
    assert "SECRET-KEY-MATERIAL" not in str(r)


def test_read_file_refuses_the_database(data_dir):
    (data_dir / "app.db").write_bytes(b"SQLite format 3\x00" + b"\x00" * 64)
    r = _run("read_file", str(data_dir / "app.db"))
    assert r.get("exit_code") == 1


def test_write_file_cannot_overwrite_settings(data_dir):
    target = data_dir / "settings.json"
    target.write_text('{"tavily_api_key": "keep"}', encoding="utf-8")
    r = _run("write_file", f"{target}\n{{}}")
    assert r.get("exit_code") == 1
    assert target.read_text(encoding="utf-8") == '{"tavily_api_key": "keep"}'


def test_read_file_still_reads_an_upload(data_dir):
    """Negative control for the three tests above."""
    (data_dir / "uploads" / "notes.txt").write_text("hello from an upload", encoding="utf-8")
    r = _run("read_file", str(data_dir / "uploads" / "notes.txt"))
    assert r.get("exit_code") == 0
    assert "hello from an upload" in r.get("output", "")


def _seed_grep(data_dir):
    (data_dir / "settings.json").write_text('{"tavily_api_key": "tvly-SECRET-1"}\n', encoding="utf-8")
    (data_dir / "cookbook_state.json").write_text('{"hf": "tvly-SECRET-2"}\n', encoding="utf-8")
    (data_dir / "uploads" / "notes.txt").write_text("tvly-public mention\n", encoding="utf-8")


@pytest.mark.parametrize("use_rg", [True, False], ids=["ripgrep", "python-fallback"])
def test_grep_never_prints_state_files(data_dir, monkeypatch, use_rg):
    if use_rg and not shutil.which("rg"):
        pytest.skip("ripgrep not installed")
    if not use_rg:
        real_which = shutil.which
        monkeypatch.setattr(shutil, "which", lambda name, *a, **k: None if name == "rg" else real_which(name, *a, **k))
    _seed_grep(data_dir)
    # Searching data/ itself is refused outright under the merged policy ...
    whole = _run("grep", f'{{"pattern": "tvly", "path": "{data_dir}"}}')
    assert "SECRET" not in str(whole)
    # ... and the readable part still answers (negative control).
    r = _run("grep", f'{{"pattern": "tvly", "path": "{data_dir / "uploads"}"}}')
    out = r.get("output", "")
    assert "notes.txt" in out, "negative control: the upload must still match"
    assert "SECRET" not in out


def test_glob_does_not_list_state_files(data_dir):
    _seed_grep(data_dir)
    whole = _run("glob", f'{{"pattern": "*.json", "path": "{data_dir}"}}')
    assert "settings.json" not in whole.get("output", "")
    assert "cookbook_state.json" not in whole.get("output", "")
    r = _run("glob", f'{{"pattern": "*.txt", "path": "{data_dir / "uploads"}"}}')
    assert "notes.txt" in r.get("output", "")


# ── through the real dispatcher, as an admin ──

@pytest.mark.asyncio
async def test_dispatch_read_file_refuses_state(data_dir, monkeypatch):
    auth_mod = sys.modules.get("core.auth")
    if auth_mod is None:
        import core.auth as auth_mod

    class _AdminAuth:
        is_configured = True

        def is_admin(self, username):
            return True

    monkeypatch.setattr(auth_mod, "AuthManager", lambda: _AdminAuth())
    monkeypatch.setattr("src.tool_execution.owner_is_admin_or_single_user", lambda owner: True)
    (data_dir / "sessions.json").write_text('{"token": "abc"}', encoding="utf-8")

    execution = _execution()
    _, result = await execution.execute_tool_block(
        SimpleNamespace(tool_type="read_file", content=str(data_dir / "sessions.json")),
        owner="admin-user",
        security_context=execution.NO_TOOL_SECURITY_CONTEXT,
    )
    assert result.get("exit_code") == 1
    assert "application state" in (result.get("error") or "")
    assert "abc" not in str(result)
