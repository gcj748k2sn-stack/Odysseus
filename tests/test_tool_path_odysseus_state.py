"""File tools must not read or write Odysseus's own state (docs/todo.md item 60).

Seen 2026-10-05 08:32/08:34 (session 726f7e32, Bonsai 2): looking for "the
last saved data", the model called read_file on data/app.db twice; the second
read pushed the next request to 36,656 tokens against a 32,768 window. DATA_DIR
is the DEFAULT root for read_file/write_file and the deny-list only knew
home-directory secrets, so the same call could have read data/.app_key (the key
that decrypts stored email passwords and tokens), sessions.json (login tokens)
or settings.json (search API keys) — and write_file could overwrite them.

Every case below runs against a temporary DATA_DIR; the negative controls are
the ordinary files in data/ that must stay readable.
"""
import asyncio
import os
import shutil
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.tool_execution import (
    _active_workspace,
    _direct_fallback,
    _is_odysseus_state_path,
    _is_sensitive_path,
    _resolve_tool_path,
)

STATE = [
    ".app_key", ".key", "auth.json", "sessions.json", "settings.json",
    "cookbook_state.json", "user_prefs.json",
    "app.db", "app.db-journal", "app.db-wal", "app.db-shm", "app.db.bak-before-bonsai2",
    "scheduled_emails.db", "chroma/chroma.sqlite3",
    "settings.json.bak", "auth.json.tmp-123", ".app_key~",
    "Auth.JSON", "APP.DB",
]
ALLOWED = [
    "uploads/report.txt", "uploads/settings.json", "personal_docs/a.md",
    "presets.json", "memory.json", "logs/app.log", "skills/notes.md",
    "hwfit/models.json", "settings.jsonx", ".keyboard", "notes.dbx",
]


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """A DATA_DIR under tmp_path (itself under the default /tmp root)."""
    data = tmp_path / "data"
    (data / "uploads").mkdir(parents=True)
    (data / "chroma").mkdir()
    monkeypatch.setattr("src.constants.DATA_DIR", str(data))
    with patch("src.settings.get_setting", return_value=[]):
        yield data


def _run(tool, content):
    return asyncio.run(_direct_fallback(tool, content))


# ── the resolver every file tool goes through ──

@pytest.mark.parametrize("rel", STATE)
def test_state_files_are_refused(data_dir, rel):
    with pytest.raises(ValueError, match="Odysseus's own state"):
        _resolve_tool_path(str(data_dir / rel))


@pytest.mark.parametrize("rel", ALLOWED)
def test_ordinary_data_files_still_resolve(data_dir, rel):
    """Negative control: the rule is the listed files, not data/ as a whole."""
    target = data_dir / rel
    assert _resolve_tool_path(str(target)) == os.path.realpath(str(target))


def test_the_same_names_outside_data_dir_are_not_state(data_dir, tmp_path):
    for rel in ("app.db", "settings.json", ".app_key"):
        assert not _is_odysseus_state_path(os.path.realpath(str(tmp_path / "elsewhere" / rel)))


def test_case_variant_spelling_of_data_dir(data_dir):
    """Default macOS: DATA/Auth.JSON opens data/auth.json, and realpath keeps
    the caller's spelling."""
    assert _is_odysseus_state_path(str(data_dir).upper() + os.sep + "AUTH.JSON")


def test_state_files_count_as_sensitive_for_grep_and_glob_filters(data_dir):
    assert _is_sensitive_path(os.path.realpath(str(data_dir / "settings.json")))
    assert not _is_sensitive_path(os.path.realpath(str(data_dir / "presets.json")))


def test_workspace_mode_refuses_state_too(data_dir, tmp_path):
    """A workspace that contains data/ (e.g. the repo itself) is a second way in."""
    token = _active_workspace.set(str(tmp_path))
    try:
        with pytest.raises(ValueError, match="Odysseus's own state"):
            _resolve_tool_path("data/auth.json")
        assert _resolve_tool_path("data/uploads/x.txt") == os.path.realpath(str(data_dir / "uploads" / "x.txt"))
    finally:
        _active_workspace.reset(token)


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
    """Negative control for the two tests above."""
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
    r = _run("grep", f'{{"pattern": "tvly", "path": "{data_dir}"}}')
    out = r.get("output", "")
    assert "notes.txt" in out, "negative control: the upload must still match"
    assert "SECRET" not in out
    assert "settings.json" not in out and "cookbook_state.json" not in out


def test_glob_does_not_list_state_files(data_dir):
    _seed_grep(data_dir)
    (data_dir / "presets.json").write_text("{}", encoding="utf-8")
    r = _run("glob", f'{{"pattern": "*.json", "path": "{data_dir}"}}')
    out = r.get("output", "")
    assert "presets.json" in out
    assert "settings.json" not in out and "cookbook_state.json" not in out


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

    from src.tool_execution import execute_tool_block
    _, result = await execute_tool_block(
        SimpleNamespace(tool_type="read_file", content=str(data_dir / "sessions.json")),
        owner="admin-user",
    )
    assert result.get("exit_code") == 1
    assert "Odysseus's own state" in (result.get("error") or "")
