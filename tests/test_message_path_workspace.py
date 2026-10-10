"""A path the user types binds a workspace when it exists and is safe.

notes/todo.md, *"A file path in a message without a workspace gets no file
tools"*: "What is the first heading in /Users/.../README.md?" bound nothing
because upstream also wanted a task word ("read", "file", ...) and kept the
trailing "?" on the path. The model then said it could not read the file.

Covers ``src/message_path_workspace.py`` and ``_resolve_workspace_from_message_path``
in ``routes/chat_routes.py``.
"""

import os

import pytest

from src import message_path_workspace as mpw


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "proj"  # not a task word (upstream gated on "repo", "file", ...)
    root.mkdir()
    (root / "README.md").write_text("# Odysseus\n")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("print(1)\n")
    return os.path.realpath(root)


# --- which paths are found ------------------------------------------------

@pytest.mark.parametrize("message, expected", [
    ("What is the first heading in /a/b/README.md?", ["/a/b/README.md"]),
    ("Summarize /a/b/notes.md.", ["/a/b/notes.md"]),
    ("How many lines does ~/x/app.py have?!", ["~/x/app.py"]),
    ("Look at `/a/b/c.py`", ["/a/b/c.py"]),
    ('Open "/a/b c" now', ["/a/b"]),
    ("(see /a/b/c)", ["/a/b/c"]),
])
def test_candidate_paths_strip_sentence_punctuation(message, expected):
    assert mpw.candidate_paths(message) == expected


@pytest.mark.parametrize("message", [
    "See https://example.com/a/b for details",
    "this and/or that",
    "ratio 1/2",
    "",
    None,
])
def test_candidate_paths_ignore_urls_and_words(message):
    assert mpw.candidate_paths(message) == []


# --- what gets bound -------------------------------------------------------

@pytest.mark.parametrize("template", [
    "What is the first heading in {readme}?",          # the live failure
    "Summarize {readme}",
    "How many lines does {app} have?",
    "Read {readme} and tell me the first heading",     # bound before, still bound
])
def test_an_existing_file_binds_its_folder_without_task_words(repo, template):
    message = template.format(
        readme=os.path.join(repo, "README.md"),
        app=os.path.join(repo, "src", "app.py"),
    )
    expected = os.path.join(repo, "src") if "app.py" in message else repo
    assert mpw.resolve(message) == expected


def test_an_existing_folder_binds_itself(repo):
    assert mpw.resolve(f"What is in {repo}?") == repo


def test_the_first_usable_path_wins(repo, tmp_path):
    missing = os.path.join(str(tmp_path), "nope", "x.md")
    assert mpw.resolve(f"Compare {missing} with {repo}/README.md") == repo


def test_a_path_that_does_not_exist_binds_nothing(tmp_path):
    assert mpw.resolve(f"What is in {tmp_path}/missing/README.md?") == ""


def test_a_sensitive_folder_binds_nothing(tmp_path):
    ssh = tmp_path / ".ssh"
    ssh.mkdir()
    (ssh / "config").write_text("Host x\n")
    assert mpw.resolve(f"What is in {ssh}/config?") == ""


def test_app_state_binds_nothing():
    from src.constants import DATA_DIR
    assert os.path.isdir(DATA_DIR)
    assert mpw.resolve(f"What is in {DATA_DIR}?") == ""


def test_the_filesystem_root_binds_nothing():
    assert mpw.resolve("What is in / ?") == ""
    assert mpw.resolve("What is in /?") == ""


def test_a_url_binds_nothing(repo):
    # The path part of the URL exists on disk, but a URL is not a local path.
    assert mpw.resolve(f"Fetch http://localhost{repo}/README.md") == ""


# --- bash ------------------------------------------------------------------

@pytest.mark.parametrize("message", [
    "What is the first heading in /a/README.md?",
    "Summarize /a/notes.md",
    "Read /a/README.md",
    "Open /a/b",
    "What is in /a/build/test/README.md?",   # action words inside the path
])
@pytest.mark.parametrize("current", [None, "false", "true"])
def test_a_question_keeps_the_requests_bash_setting(message, current):
    assert mpw.bash_setting(message, current) == current


@pytest.mark.parametrize("message", [
    "Run the tests in /a/repo",
    "Extract the subtitles from /a/movie.mkv",
    "Convert /a/x.wav to mp3",
    "Fix the build in /a/repo",
])
def test_an_action_turns_bash_on(message):
    assert mpw.bash_setting(message, "false") == "true"
    assert mpw.bash_setting(message, None) == "true"


# --- the route function ----------------------------------------------------

def _route(monkeypatch, *, admin):
    from routes import chat_routes
    import src.tool_security as tool_security
    monkeypatch.setattr(chat_routes, "get_current_user", lambda _request: "alice")
    monkeypatch.setattr(tool_security, "owner_is_admin_or_single_user", lambda _owner: admin)
    return chat_routes._resolve_workspace_from_message_path


def test_route_binds_for_an_admin(monkeypatch, repo):
    resolve = _route(monkeypatch, admin=True)
    assert resolve(object(), f"What is the first heading in {repo}/README.md?") == (repo, "")


def test_route_binds_nothing_for_a_non_admin(monkeypatch, repo):
    resolve = _route(monkeypatch, admin=False)
    assert resolve(object(), f"What is the first heading in {repo}/README.md?") == ("", "")


def test_route_skips_the_owner_check_without_a_path(monkeypatch):
    from routes import chat_routes
    import src.tool_security as tool_security

    def explode(_owner):
        raise AssertionError("owner check ran for a message without a path")

    monkeypatch.setattr(chat_routes, "get_current_user", lambda _request: "alice")
    monkeypatch.setattr(tool_security, "owner_is_admin_or_single_user", explode)
    assert chat_routes._resolve_workspace_from_message_path(object(), "hello there") == ("", "")
