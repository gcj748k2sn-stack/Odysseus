"""A turn that called no tools at all — notes/todo.md items 8, 6 and 9.

Run fd0f9ba0, 2026-07-28, was the third identical request in ten minutes and
produced no document. Its last turn read, in full:

    I'll create a new comprehensive document about pink oyster mushroom growth
    phases with detailed cultivation guidance:

380 seconds, no tool call, nothing created, and **the user was told nothing** —
past two guards that both exist to prevent exactly this.

Neither guard was broken; both were out of range:

* `_gathering_only_notice` returns "" when no tool ran, so it can only ever fire
  on a turn that ran at least one.
* `_text_is_only_preamble` is positional — "text written before the tool ran
  cannot describe what the tool did" — and a turn with no tools has no boundary
  to be positional about.

Item 8 records its reporting half as verified live on run eb2d0ac1, which ran
three tools. **That verification was real and its scope was narrower than the
item claimed**, which is the thing this project keeps paying for: record what a
fix was verified against, not just that it was.

It also pins `round_texts`, which is persisted for the same reason items 10
and 17 exist: a fault nobody can see in the record is a fault that gets
re-diagnosed as something else. (The stream-failure half — `stream_errors` in
the metrics and its notice — was retired after the 2026-10-06 merge: upstream
now ends a failed stream with `[Agent stopped: …]` and records `failed` /
`failure` itself, and the fork's path became unreachable.)
"""
import pytest

from src.agent_loop import _compute_final_metrics
from src.turn_report import (
    _gathering_only_notice,
    _unstarted_promise_notice,
)

# The exact text, from app.db.
FD0F9BA0 = (
    "I'll create a new comprehensive document about pink oyster mushroom "
    "growth phases with detailed cultivation guidance:"
)


# ── the gap ──────────────────────────────────────────────────────────────────

def test_the_older_guard_still_cannot_see_a_zero_tool_turn():
    """Not a regression — the documented reason the new guard has to exist.

    If this ever starts returning a notice, the two guards have begun to
    overlap and one of them should go.
    """
    assert _gathering_only_notice([]) == ""


def test_the_recorded_turn_is_now_reported():
    notice = _unstarted_promise_notice(FD0F9BA0, [])
    assert notice
    assert "nothing was created or changed" in notice
    assert "called no tools" in notice


def test_the_notice_does_not_claim_any_tool_ran():
    """`_gathering_only_notice` names the tools it ran. This one must not —
    there were none, and a notice that invents them is worse than silence."""
    notice = _unstarted_promise_notice(FD0F9BA0, [])
    for word in ("I ran", "web_search", "web_fetch", "gathered"):
        assert word not in notice


# ── what it must not fire on ─────────────────────────────────────────────────

def test_a_turn_that_used_tools_is_left_to_the_other_guard():
    assert _unstarted_promise_notice(FD0F9BA0, [{"tool": "web_fetch"}]) == ""


def test_a_complete_answer_is_untouched():
    assert _unstarted_promise_notice("Created **Pink Oyster Growth Phases** (v1).", []) == ""


def test_a_question_is_not_a_dangling_promise():
    """fd0f9ba0's *other* turn ended by offering three options and a question
    mark. It declined to act, said so, and that is a complete answer."""
    text = (
        "This document already exists. Would you like me to:\n"
        "1. Add sections?\n2. Edit content?\n3. Create a summary?"
    )
    assert _unstarted_promise_notice(text, []) == ""


def test_an_empty_response_is_left_to_the_empty_response_fallback():
    assert _unstarted_promise_notice("", []) == ""
    assert _unstarted_promise_notice("   \n ", []) == ""


def test_a_colon_inside_the_text_is_not_a_colon_at_the_end():
    text = "Here are the phases:\n\n1. Colonisation\n2. Pinning\n3. Fruiting"
    assert _unstarted_promise_notice(text, []) == ""


# ── the diagnostic fields ────────────────────────────────────────────────────

def _metrics(**kw):
    base = dict(
        messages=[], full_response="hi", total_duration=1.0, time_to_first_token=0.5,
        context_length=32768, real_input_tokens=10, real_output_tokens=2,
        has_real_usage=True, tool_events=[], round_texts=["some round text"],
    )
    base.update(kw)
    return _compute_final_metrics(**base)


def test_round_texts_is_recorded_without_any_tool_events():
    """The field that separates item 6 from item 8.

    It used to be nested under `if tool_events:`, so it was absent from exactly
    the turns where the question arises — a short message and no way to tell
    whether the model wrote that much or the save path deleted the rest.
    """
    assert _metrics(tool_events=[])["round_texts"] == ["some round text"]


def test_round_texts_is_still_recorded_alongside_tool_events():
    m = _metrics(tool_events=[{"tool": "web_fetch"}])
    assert m["round_texts"] == ["some round text"]
    assert m["tool_events"] == [{"tool": "web_fetch"}]


def test_no_round_texts_means_no_key_rather_than_an_empty_list():
    assert "round_texts" not in _metrics(round_texts=[])
