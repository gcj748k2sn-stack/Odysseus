"""A turn that only gathered information must not report "Done.".

Runs dd3e7371 and 0b12aadb (2026-07-19) — the same request, twice:

    "extract html,css and javascript out of martha9_1.ino and create a new
     index.html with the extracted content"

0b12aadb ran `glob` (found the .ino), then `read_file` (10,035 chars), reasoned
correctly that the sketch embeds an HTML page — its thinking ends *"I'll create
a standalone index.html ... Let me write out the extracted content:"* — and then
emitted nothing. 393 seconds, 154 output tokens, no `write_file`, no file. Saved
as **"Done."** The user retried the task four times in 16 minutes.

This is the "Done." bug on a non-document tool path. The earlier fix keyed off
DOC_TOOLS, and `_empty_response_fallback` returned early whenever `tool_events`
was non-empty, so read-only turns fell straight through to
`routes/chat_routes.py:1495`.

Scope note: this guard covers the EMPTY-response case only. Runs f14a8f52 and
1ca0cdc0 wrote a dangling promise ("Let me first explore your workspace…") and
then stopped — non-empty response, so nothing here fires. That is a
stops-early problem, tracked separately in notes/todo.md.
"""

import json

from src.agent_loop import _empty_response_fallback
from src.turn_report import (
    READ_ONLY_TOOLS,
    _gathering_only_notice,
)


def _delta(chunk):
    assert chunk.startswith("data: ")
    return json.loads(chunk[len("data: "):])["delta"]


# --------------------------------------------------------------------------
# The observed failures
# --------------------------------------------------------------------------

def test_glob_then_read_file_then_silence_is_reported(monkeypatch):
    """Run 0b12aadb exactly."""
    events = [
        {"round": 1, "tool": "glob", "output": "/Users/c/martha9_1.ino"},
        {"round": 2, "tool": "read_file", "output": "// HTML page ..."},
    ]
    notice = _gathering_only_notice(events)
    assert notice.strip() != "Done."
    assert "nothing was created or changed" in notice.lower()
    assert "`glob`" in notice and "`read_file`" in notice


def test_glob_only_then_silence_is_reported():
    """Run dd3e7371: found the file, then stopped."""
    events = [{"round": 1, "tool": "glob", "output": "/Users/c/martha9_1.ino"}]
    notice = _gathering_only_notice(events)
    assert notice.strip() != "Done."
    assert "`glob`" in notice


def test_workspace_listing_turn_is_reported():
    events = [
        {"round": 1, "tool": "get_workspace", "output": "/Users/c/x"},
        {"round": 2, "tool": "ls", "output": "martha9_1/"},
    ]
    assert "nothing was created or changed" in _gathering_only_notice(events).lower()


def test_each_tool_named_once_in_order():
    events = [
        {"tool": "glob"}, {"tool": "read_file"},
        {"tool": "read_file"}, {"tool": "glob"},
    ]
    notice = _gathering_only_notice(events)
    assert notice.index("`glob`") < notice.index("`read_file`")
    assert notice.count("`glob`") == 1
    assert notice.count("`read_file`") == 1


# --------------------------------------------------------------------------
# What must NOT fire — the expensive direction to get wrong
# --------------------------------------------------------------------------

def test_effectful_tool_keeps_previous_behaviour():
    """A quiet turn that WROTE something is a success, not a failure.

    Telling a user "nothing was created" after write_file actually wrote is a
    worse error than the bug being fixed.
    """
    events = [{"tool": "read_file"}, {"tool": "write_file"}]
    assert _gathering_only_notice(events) == ""


def test_unknown_tool_is_never_assumed_read_only():
    """MCP/cookbook/future tools must not be guessed at.

    An unrecognised tool could have sent an email or moved money; claiming
    nothing happened would be a lie. Guard stays quiet.
    """
    for unknown in ("mcp__email__send_email", "serve_model", "some_future_tool"):
        assert _gathering_only_notice([{"tool": "glob"}, {"tool": unknown}]) == ""


def test_document_tools_are_not_in_the_read_only_set():
    """They change documents, and they have their own reporting path."""
    for t in ("create_document", "update_document", "edit_document", "suggest_document"):
        assert t not in READ_ONLY_TOOLS


def test_no_tools_at_all_is_untouched():
    """Pure empty response keeps the original message."""
    response, chunk = _empty_response_fallback("", "", [])
    assert "empty response" in response
    assert chunk is not None


def test_model_that_answered_is_left_alone():
    """Read-only tools plus a real answer is a normal Q&A turn.

    The loop only consults the notice when the stripped response is empty;
    _empty_response_fallback must not touch an answered turn.
    """
    events = [{"tool": "ls"}]
    response, chunk = _empty_response_fallback("You have 3 files.", "", events)
    assert response == "You have 3 files."
    assert chunk is None


def test_reasoning_only_fallback_still_works():
    assert _empty_response_fallback("", "thought hard", [])[0] == "thought hard"


def test_document_edit_failure_notice_still_takes_precedence():
    """Both could match; the document-specific one is more informative, and it
    runs first (in _empty_response_fallback, before strip_tool_blocks)."""
    events = [{"tool": "read_file"}]
    response, _ = _empty_response_fallback(
        "", "", events, doc_edit_failures=1, doc_edit_error="no content",
    )
    assert "document is unchanged" in response.lower()
