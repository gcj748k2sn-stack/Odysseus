"""Closing report for turns that ran a side-effecting non-document tool.

notes/todo.md item 11. Behavioural, per `tests/TESTING_STANDARD.md`: every test
here drives `_side_effect_tool_summary` with `tool_events` shaped exactly as
`app.db` records them, and asserts on what a user would read.

**The negative controls are the point of the file.** A checker with only
positive cases can be a function that always fires and still look like it
works (notes/todo.md item 16, and the false positives the document-fidelity
sweep caught). Four inputs here MUST produce nothing: read-only turns,
document turns, self-reporting turns, and a successful turn the model already
described.

**Measured against the whole recorded corpus before shipping**, not just
against these fixtures — 77 recorded assistant turns, 72 with tool events.
Seven would produce a line. Five of those seven were saved as a bare
**"Done."** with `round_texts` all zero (the model wrote nothing at all), and
the other two as a 174/175-character preamble written before any tool ran.
**Zero of the seven had a reply that described the work**, so on this corpus
the report never duplicates anything the user was already told. One of the
five "Done." turns is `write_file` returning *"Wrote 0 bytes"* — a file
emptied, reported as success, in the run range item 8's reverted nudge covers.
"""

import pytest

from src.agent_loop import (
    _first_line,
    _gathering_only_notice,
    _side_effect_tool_summary,
    _tool_event_failed,
    _unstarted_promise_notice,
)


def ev(tool, output="", exit_code=0, **extra):
    """A tool event shaped the way `_compute_final_metrics` persists one."""
    return {"tool": tool, "output": output, "exit_code": exit_code, **extra}


# ── The recorded failure this exists for ────────────────────────────────────

def test_the_recorded_session_57dcd968_turn_is_reported():
    """Verbatim from `app.db`, 2026-07-28: web_fetch → write_file → get_workspace.

    The saved reply was the 175-character preamble and nothing else. todo.md
    filed this as a file written and not reported; the tool result says the
    write was REFUSED. Both halves matter — the report has to name the failure
    and quote the reason, because the reason is the fix.
    """
    events = [
        ev("web_fetch", "# martha (static)\nSource: http://192.168.0.185", 0),
        ev(
            "write_file",
            "write_file: path 'TEMPERATURE_HUMIDITY_READINGS.md' is outside "
            "the allowed roots",
            1,
        ),
        ev("get_workspace", "No workspace is set.", 0),
    ]
    out = _side_effect_tool_summary(events)

    assert "`write_file` failed" in out
    assert "outside the allowed roots" in out
    # The read-only tools in the same turn are not this function's business —
    # `_gathering_only_notice` owns those, and duplicating them would make the
    # two guards fight over the same turn.
    assert "web_fetch" not in out
    assert "get_workspace" not in out


def test_the_existing_guards_really_do_miss_that_turn():
    """Check the guard fails before checking that it passes.

    Without this, the test above proves only that the new function returns a
    string — not that anything was broken. Both existing guards must stay
    silent on the recorded turn, for the two different reasons todo.md item 11
    gives. If either starts firing, the new report becomes a duplicate and
    this test is where that shows up.
    """
    preamble = (
        "I'll fetch data from `http://192.168.0.185` and create a comprehensive "
        "document with temperature/humidity readings over time (with current "
        "snapshot + notes about limitations)."
    )
    events = [
        ev("web_fetch", "# martha (static)", 0),
        ev("write_file", "write_file: path '…' is outside the allowed roots", 1),
        ev("get_workspace", "No workspace is set.", 0),
    ]
    # A mutating tool ran, so the read-only guard declines.
    assert _gathering_only_notice(events) == ""
    # Tools ran, so the zero-tool guard declines.
    assert _unstarted_promise_notice(preamble, events) == ""
    # And the new one does not.
    assert _side_effect_tool_summary(events) != ""


def test_a_failure_survives_a_confident_model_summary():
    """Item 21's argument, non-document path.

    A model that sounds sure must not be able to suppress the report of a tool
    that failed. `failures_only=True` is what the turn-end path passes when the
    model wrote its own summary.
    """
    events = [ev("write_file", "write_file: permission denied", 1)]
    out = _side_effect_tool_summary(events, failures_only=True)
    assert "`write_file` failed" in out
    assert "permission denied" in out


def test_a_success_is_not_repeated_when_the_model_already_reported_it():
    """The other half of the same switch — and the reason it is a switch.

    Reporting a success the model just described would put the same fact on
    screen twice. Reporting a failure it ignored is the whole feature.
    """
    events = [ev("write_file", "Wrote 3791 bytes to /Users/c/Desktop/index.html", 0)]
    assert _side_effect_tool_summary(events, failures_only=True) == ""
    assert "3791 bytes" in _side_effect_tool_summary(events, failures_only=False)


# ── Negative controls: these must produce nothing ───────────────────────────

def test_negative_control_read_only_turn_reports_nothing():
    """`_gathering_only_notice` owns this shape. Two guards on one turn would
    contradict each other in the same reply."""
    events = [ev("web_search", "```sources\n[1] …"), ev("read_file", "…"),
              ev("glob", "./x.ino"), ev("ls", "a\nb")]
    assert _side_effect_tool_summary(events) == ""


def test_negative_control_document_turn_reports_nothing():
    """`_doc_tool_summary` owns document tools, and carries the item 2a/2b/3
    warnings with them. A second summary here would drop those warnings while
    looking like a report."""
    events = [ev("create_document", 'Document created: "X" (v1)', None),
              ev("edit_document", "2 edits applied", None)]
    assert _side_effect_tool_summary(events) == ""


def test_negative_control_self_reporting_tools_stay_silent():
    """The end-of-turn path REPLACES `full_response` with these tools' output.
    Anything appended before that is discarded, so a line built here would be
    written and never seen."""
    for tool in ("manage_notes", "manage_calendar", "manage_tasks",
                 "list_emails", "read_email"):
        assert _side_effect_tool_summary([ev(tool, "…output…")]) == "", tool


def test_negative_control_no_tools_at_all():
    assert _side_effect_tool_summary([]) == ""
    assert _side_effect_tool_summary(None) == ""


def test_negative_control_document_success_is_not_read_as_failure():
    """Document tools record `exit_code=None`. An `!= 0` test would flag every
    successful `create_document` in the corpus as a failure."""
    assert _tool_event_failed(ev("create_document", "ok", None)) is False
    assert _tool_event_failed(ev("write_file", "ok", 0)) is False
    assert _tool_event_failed(ev("write_file", "no", 1)) is True


# ── The zero-byte write ─────────────────────────────────────────────────────

def test_a_zero_byte_write_is_flagged_even_though_it_succeeded():
    """Recorded 2026-07-17: `write_file` returned exit 0 and "Wrote 0 bytes".

    Exit status says success; the file is empty. This is the shape item 8's
    reverted nudge produced five times in four minutes, and an exit-code-only
    report would call it a success.
    """
    events = [ev("write_file", "Wrote 0 bytes to /Users/c/Desktop/index.html", 0)]
    out = _side_effect_tool_summary(events)
    assert "0 bytes" in out
    assert "empty" in out.lower()


def test_a_normal_write_is_not_flagged_as_empty():
    """Negative control for the check above — "Wrote 10 bytes" must not match
    a sloppy "0 bytes" substring test."""
    out = _side_effect_tool_summary([ev("write_file", "Wrote 10 bytes to /x", 0)])
    assert "empty" not in out.lower()
    out = _side_effect_tool_summary([ev("write_file", "Wrote 1024 bytes to /x", 0)])
    assert "empty" not in out.lower()


# ── Coverage of tools nobody has filed yet ──────────────────────────────────

def test_an_unknown_tool_still_gets_a_line():
    """Coverage is the inverse of READ_ONLY_TOOLS on purpose. Guessing wrong
    here costs one extra line quoting a tool's own output; guessing wrong the
    other way is item 11 all over again for every tool not yet filed."""
    out = _side_effect_tool_summary([ev("some_future_tool", "did a thing")])
    assert "some_future_tool" in out and "did a thing" in out


def test_an_mcp_tool_is_named_not_left_as_mcp():
    """`_resolved_tool_event_name` digs the real name out of an `mcp` event."""
    out = _side_effect_tool_summary(
        [{"tool": "mcp", "desc": "mcp__linear__create_issue: {}",
          "output": "Created ENG-42", "exit_code": 0}]
    )
    assert "mcp__linear__create_issue" in out
    assert "Created ENG-42" in out


def test_several_tools_render_as_a_list_one_renders_as_a_line():
    one = _side_effect_tool_summary([ev("bash", "./x.ino")])
    assert not one.startswith("- ")
    many = _side_effect_tool_summary([ev("bash", "./x.ino"), ev("write_file", "Wrote 5 bytes to /x")])
    assert many.startswith("- ") and many.count("\n") == 1


# ── Output handling ─────────────────────────────────────────────────────────

def test_a_failure_with_no_output_still_says_it_failed():
    """Silence from the tool must not become silence to the user."""
    out = _side_effect_tool_summary([ev("bash", "", 1)])
    assert "`bash` failed" in out


@pytest.mark.parametrize("raw,expected", [
    ("", ""),
    (None, ""),
    ("\n\n  first  \nsecond", "first"),
    ("x" * 300, "x" * 180 + "…"),
])
def test_first_line_extraction(raw, expected):
    assert _first_line(raw) == expected


def test_long_tool_output_is_truncated_in_the_report():
    out = _side_effect_tool_summary([ev("bash", "y" * 500, 1)])
    assert len(out) < 260
    assert "…" in out
