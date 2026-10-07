"""Closing summary for turns that end on a document tool.

Background: the doc-finetune path breaks the agent loop as soon as a document
tool succeeds (`_ody_doc_tool_completed` in src/agent_loop.py), so the model
never gets a round to say what it changed. Turns therefore surfaced as a bare
"Done." — observed live on runs 11ea1727, 88af1770 and 127d32b0 (2026-07-18),
where the *only* thing the user wanted was the list of corrections.

These pin the synthesized summary, which is derived from the tool result
instead of an extra LLM round.
"""

from src.turn_report import _doc_tool_summary


def test_create_reports_title_and_version():
    out = _doc_tool_summary({
        "tool": "create_document",
        "title": "Pink Oyster Mushroom Growth Phases Guide",
        "version": 1,
    })
    assert out == "Created **Pink Oyster Mushroom Growth Phases Guide** (v1)."


def test_edit_reports_applied_count():
    # Mirrors run 127d32b0 turn 2: edit_document -> (v2, 8 edit(s)).
    out = _doc_tool_summary({
        "tool": "edit_document",
        "title": "Pink Oyster Mushroom Growth Phases Guide",
        "version": 2,
        "applied": 8,
        "skipped": 0,
    })
    assert "Updated **Pink Oyster Mushroom Growth Phases Guide** (v2)" in out
    assert "8 edits applied" in out
    assert "not applied" not in out


def test_partially_applied_edit_is_surfaced_loudly():
    """edit_document returns success whenever >=1 FIND block matched, so a
    partial application used to be completely silent. That is the mechanism
    behind the self-contradicting documents (a corrected value in one place,
    the stale value still sitting in the summary table)."""
    out = _doc_tool_summary({
        "tool": "edit_document",
        "title": "Guide",
        "version": 4,
        "applied": 6,
        "skipped": 3,
    })
    assert "6 edits applied" in out
    assert "3 not applied" in out
    assert "still missing" in out


def test_singular_edit_is_not_pluralized():
    out = _doc_tool_summary({
        "tool": "update_document", "title": "Guide", "version": 2,
        "applied": 1, "skipped": 0,
    })
    assert "1 edit applied" in out


def test_suggest_makes_clear_nothing_changed_yet():
    out = _doc_tool_summary({
        "tool": "suggest_document", "title": "Guide", "version": 3,
    })
    assert "nothing changed until you accept" in out


def test_stale_values_are_called_out_as_a_contradiction():
    """The half-corrected document case. Reporting plain success here is what
    let run 127d32b0 ship a doc carrying four different CO2 thresholds."""
    out = _doc_tool_summary({
        "tool": "edit_document", "title": "Guide", "version": 4,
        "applied": 9, "skipped": 0, "stale_values": ["0.4%", "15-20°C"],
    })
    assert "9 edits applied" in out
    assert "Still inconsistent" in out
    assert "`0.4%`" in out and "`15-20°C`" in out
    assert "contradicts itself" in out


def test_single_stale_value_uses_singular_grammar():
    out = _doc_tool_summary({
        "tool": "edit_document", "title": "Guide", "version": 4,
        "applied": 3, "skipped": 0, "stale_values": ["0.4%"],
    })
    assert "was corrected" in out and "still appears" in out


def test_stale_value_list_is_truncated():
    out = _doc_tool_summary({
        "tool": "edit_document", "title": "Guide", "version": 2,
        "applied": 8, "skipped": 0,
        "stale_values": [f"{n}%" for n in range(1, 10)],
    })
    assert "+3 more" in out


def test_clean_edit_has_no_warning_block():
    out = _doc_tool_summary({
        "tool": "edit_document", "title": "Guide", "version": 2,
        "applied": 8, "skipped": 0, "stale_values": [],
    })
    assert "Still inconsistent" not in out
    assert out.endswith(".")


def test_empty_info_falls_back_so_caller_can_use_done():
    assert _doc_tool_summary({}) == ""


def test_missing_title_does_not_emit_empty_bold():
    out = _doc_tool_summary({"tool": "edit_document", "applied": 2, "skipped": 0})
    assert "****" not in out
    assert "the document" in out
