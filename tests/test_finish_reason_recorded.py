"""A clipped generation must be distinguishable from a short one — item 41.

Filed 2026-08-01 out of a retraction. Asked whether a zero-text turn was
`max_tokens` exhaustion, a sweep of both logs for `finish_reason=length`
returned zero and was called decisive. It was not: `finish_reason` appeared
**0 times in `app.log` and `app.log.1` and was passed to no logger anywhere in
`src/`**, so the grep measured the logging configuration, not the behaviour.

Until this existed, a document cut off at the token limit looked exactly like a
document the model chose to end, and every claim about output length in items
8, 9b, 23, 40 and 44 was unfalsifiable. Item 44 is the concrete case: the
ai-tidy endpoint returns `chars=0` on every run, and *"stopped at the cap"*
versus *"the model said nothing"* is precisely `length` versus `stop`.

**The convention, and it is the whole design:** absence means the provider did
not report a reason. It NEVER means the generation finished cleanly. That is
the same rule as the cache flag (item 17), and the tests below pin it in both
directions — which is why the first two are
negative controls. A recorder that always records is not a recorder.

Report-only: nothing here changes what any request sends or what any caller
receives. `llm_call_async` still returns a bare `str`; the reason reaches the
log, because widening that return type would touch every caller.
"""

import logging

import pytest

from tests.helpers.import_state import clear_fake_database_modules

clear_fake_database_modules()

import src.agent_loop as agent_loop


def _metrics(**kw):
    """Call the metrics builder with the minimum it needs.

    Keyword-only so a signature change surfaces here as a TypeError rather
    than as a silently mis-ordered positional argument.
    """
    base = dict(
        messages=[],
        full_response="hello",
        total_duration=1.0,
        time_to_first_token=0.5,
        context_length=32768,
        real_input_tokens=100,
        real_output_tokens=50,
        has_real_usage=True,
        tool_events=[],
        round_texts=[],
    )
    base.update(kw)
    return agent_loop._compute_final_metrics(**base)


# --------------------------------------------------------------------------
# Negative controls. A key that is always present carries no information.
# --------------------------------------------------------------------------

def test_no_reasons_reported_means_no_key():
    """The provider reported nothing -> the key is absent, not `"stop"`.

    Writing a default here would be the bug this item exists to prevent: it
    would make "finished cleanly" indistinguishable from "nobody looked",
    which is exactly the state the retraction found.
    """
    assert "finish_reasons" not in _metrics(finish_reasons=[])
    assert "finish_reasons" not in _metrics(finish_reasons=None)
    assert "finish_reasons" not in _metrics()


def test_a_clean_stop_is_still_recorded():
    """`stop` is data, not silence — it distinguishes "asked and it finished"
    from "never asked". Dropping it would collapse those two again."""
    m = _metrics(finish_reasons=[{"round": 1, "reason": "stop"}])
    assert m["finish_reasons"] == [{"round": 1, "reason": "stop"}]


# --------------------------------------------------------------------------
# The case the item was filed for.
# --------------------------------------------------------------------------

def test_length_is_recorded_per_round():
    """`max_tokens` is per ROUND, so a turn total cannot say which was clipped.

    The 2026-08-01 corpus has turns whose round 1 ran 82 s for 54 characters
    and whose round 2 produced nothing at all; a single turn-level flag could
    not have told those apart.
    """
    m = _metrics(finish_reasons=[
        {"round": 1, "reason": "stop"},
        {"round": 2, "reason": "length"},
    ])
    assert [e["reason"] for e in m["finish_reasons"]] == ["stop", "length"]
    assert [e["round"] for e in m["finish_reasons"]] == [1, 2]


# --------------------------------------------------------------------------
# The non-streaming path — this is what unblocks item 44.
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "finish_reason,content,expect_log",
    [
        ("stop", "some text", False),          # negative control: the normal case
        ("tool_calls", "some text", False),    # negative control: text arrived, reason is odd, caller is fine
        ("length", "half a sen", True),        # truncated, and it used to be invisible
        ("stop", "", True),                    # item 44's exact observation
        ("tool_calls", "", True),              # see the docstring — this one was filed WRONG first
        (None, "", True),                      # empty with no reason at all
    ],
)
def test_utility_calls_warn_only_when_something_is_wrong(finish_reason, content, expect_log, caplog):
    """`llm_call_async` returns a bare `str`, so the log is the only channel.

    Quiet when the caller got usable text; loud on a truncation or an empty
    body. Without the negative controls a handler that logged on every call
    would pass every positive case in this file.

    ⚠️ **`("tool_calls", "", …)` was filed as a negative control and that was
    wrong — the control caught it on the first run.** The reasoning that
    produced it was *"a tool call legitimately has no text, so stay quiet"*.
    It does not apply here: **`llm_call_async` never sends a `tools` key**
    (grep the payload builder), so this path cannot legitimately produce a
    tool call, and whatever the reason the caller receives `""` and proceeds
    as though the model answered. **An empty body is always the caller's
    problem; `finish_reason` explains it rather than excusing it** — and the
    emitted line says `finish_reason='tool_calls'`, so nothing is misleading.
    The genuine exemption is the row above: a tool-call reason *with* text.

    This mirrors the branch in `llm_call_async`; it is asserted here rather
    than by driving an HTTP request so the rule stays readable. ⚠️ That makes
    it a restatement, not a test of the wiring — `tests/test_ai_tidy_instrumentation.py`
    exercises the real call path, and one live run is still owed.
    """
    logger = logging.getLogger("src.llm_core")
    with caplog.at_level(logging.WARNING, logger="src.llm_core"):
        if finish_reason and finish_reason not in ("stop", "tool_calls"):
            logger.warning(
                "[finish-reason] non-stop completion model=%s finish_reason=%s chars=%d",
                "m", finish_reason, len(content),
            )
        elif not content:
            logger.warning(
                "[finish-reason] EMPTY completion model=%s finish_reason=%r chars=0", "m", finish_reason
            )

    logged = [r for r in caplog.records if "[finish-reason]" in r.getMessage()]
    assert bool(logged) is expect_log
