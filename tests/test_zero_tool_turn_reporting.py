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

It also pins what that turn's record could not say. **`app.log` had the
mechanism the whole time** — `stream_error … {"error": "Read timeout", "status":
504}` at 380.673 s — while `app.db` held 29 output tokens at 0.09 tok/s, which
reads as a slow turn rather than a failed one. `round_texts` and `stream_errors`
are both persisted now, for the same reason items 10 and 17 exist: a fault
nobody can see in the record is a fault that gets re-diagnosed as something
else.
"""
import pytest

from src.agent_loop import (
    _compute_final_metrics,
    _gathering_only_notice,
    _stream_error_detail,
    _stream_failure_notice,
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


FD0F9BA0_ERROR = (
    'event: error\ndata: {"error": "Read timeout", "status": 504}\n\n'
)


def test_the_recorded_timeout_is_parsed_into_something_readable():
    assert _stream_error_detail(FD0F9BA0_ERROR) == "Read timeout (504)"


def test_an_unparseable_error_is_still_recorded_as_an_error():
    """Silence reads as success here, so a bad payload must not become ""."""
    assert _stream_error_detail("event: error\ndata: not json at all")
    assert _stream_error_detail("event: error\n")  # no data line at all


def test_a_failed_turn_says_so():
    notice = _stream_failure_notice([
        {"round": 1, "elapsed": 380.67, "detail": "Read timeout (504)"}
    ])
    assert "Read timeout (504)" in notice
    assert "381s" in notice  # 380.67 rounded, matching what the log reported
    assert "did not finish" in notice


def test_a_clean_turn_gets_no_failure_notice():
    assert _stream_failure_notice([]) == ""


def test_a_failure_after_real_work_does_not_claim_nothing_happened():
    """Run bbde3e51 turn 4, 2026-07-28.

    Rounds 1–3 searched, fetched and wrote **v6 of a real document**; round 4's
    stream returned a 502. The first version of this notice told the user the
    turn "did not finish, so treat it as incomplete rather than as an answer" —
    which reads as *nothing landed* about a turn that changed a file on disk.
    **A failure notice that overstates the failure is still a false report**,
    and it is the `"Done."` bug pointing the other way.
    """
    errs = [{"round": 4, "elapsed": 69.83,
             "detail": "All model candidates returned no substantive output (502)"}]
    notice = _stream_failure_notice(errs, [{"tool": "edit_document"}])
    assert "502" in notice
    assert "has been kept" in notice
    assert "the tool results above are real" in notice
    assert "did not finish" not in notice
    assert "treat it as incomplete" not in notice


def test_a_failure_with_no_tool_results_still_says_the_turn_produced_nothing():
    """The negative control for the branch above — fd0f9ba0 and bbde3e51 turn 1
    both failed having run no tools at all, and must not be softened."""
    errs = [{"round": 1, "elapsed": 375.24, "detail": "Read timeout (504)"}]
    for empty in ([], None):
        notice = _stream_failure_notice(errs, empty)
        assert "did not finish" in notice
        assert "has been kept" not in notice


def test_stream_errors_reach_the_metrics():
    errs = [{"round": 1, "elapsed": 380.67, "detail": "Read timeout (504)"}]
    assert _metrics(stream_errors=errs)["stream_errors"] == errs


def test_absence_of_the_key_means_the_stream_raised_nothing():
    """Same convention as item 17's cache flag: absent = clean, not unknown."""
    assert "stream_errors" not in _metrics(stream_errors=[])
    assert "stream_errors" not in _metrics()


def test_a_failed_turn_is_not_readable_as_a_merely_slow_one():
    """The property the retired throughput item needed and did not have.

    Both rows below are 29 tokens in 380 s — identical `tokens_per_second`,
    identical `response_time`. One model generated slowly; the other returned a
    504. Three sessions of "throughput" analysis were built on rows that could
    not tell these apart.
    """
    slow = _metrics(total_duration=380.0, real_output_tokens=29)
    failed = _metrics(total_duration=380.0, real_output_tokens=29,
                      stream_errors=[{"round": 1, "elapsed": 380.67,
                                      "detail": "Read timeout (504)"}])
    assert slow["tokens_per_second"] == failed["tokens_per_second"]
    assert "stream_errors" not in slow and "stream_errors" in failed
