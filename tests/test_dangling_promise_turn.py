"""A turn that promises, gathers, and then stops must not pass as an answer.

`tests/test_gathering_only_turn.py` covers the EMPTY-response case and closes
with a scope note: *"Runs f14a8f52 and 1ca0cdc0 wrote a dangling promise … and
then stopped — non-empty response, so nothing here fires. That is a stops-early
problem, tracked separately."* This is that problem — notes/todo.md item 8.

Observed again, and measured, on run 4e217ae0 turn 3 (2026-07-19). The user
asked "fact check and correct the document" for the second time. The model
wrote:

    "I'll fact-check this document by searching for verified mycological data
     on *Pleurotus djamor* (pink oyster) cultivation timelines and parameters."

…then ran `web_search` and two `web_fetch` calls, and stopped. 162 seconds, 542
output tokens, no `edit_document`, document untouched. Every end-of-turn guard
let it through because that opening sentence made `full_response` non-empty.

Two things were wrong. **Only the second is fixed.**

* **The promise is invisible to the per-round supervisor.** `_INTENT_RE` only
  inspects the CURRENT round's text, and the promise was written in an earlier
  round — before the tools ran. The loop now snapshots the prose before every
  tool block, so a stall is detectable regardless of which round produced it.

* **The end-of-turn notice required an empty response.** It now also fires when
  every word predates the tools, and is appended rather than replacing the
  model's own opening.

**The active half — pushing one more round — was tried and REVERTED the same
day.** Run 8c80cf8d: told to *"finish the job NOW using the appropriate tool"*,
the model called `update_document` with empty content and wiped a 6186-character
document, then created two empty documents and emptied one twice. Five
zero-length versions in four minutes, against none in the preceding 79.
Detecting and reporting a stall is safe; commanding an idle model to act is not.
See `tests/test_document_tools_reject_empty_writes.py`.

Detection is positional, not lexical — no keyword matching on "I'll" or "Let
me", which would be brittle and English-only.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.turn_report import (  # noqa: E402
    _gathering_only_notice,
    _text_is_only_preamble,
)

AGENT_LOOP_SRC = (ROOT / "src/agent_loop.py").read_text()

# The exact text from run 4e217ae0 turn 3.
PROMISE = ("I'll fact-check this document by searching for verified mycological "
           "data on *Pleurotus djamor* (pink oyster) cultivation timelines and "
           "parameters.")
TURN3_TOOLS = [
    {"tool": "web_search"},
    {"tool": "web_fetch"},
    {"tool": "web_fetch"},
]


# --- the promise must be recognised as a stall --------------------------------

def test_4e217ae0_turn3_is_recognised_as_a_stall():
    # Nothing was written after the tools ran, so the whole response predates them.
    assert _text_is_only_preamble(PROMISE, PROMISE) is True


def test_a_turn_that_actually_answered_is_left_alone():
    answered = PROMISE + "\n\nThe fruiting range is correct at 20-30°C; no change needed."
    assert _text_is_only_preamble(answered, PROMISE) is False


def test_tool_fences_do_not_count_as_writing_something():
    """The model emitting a tool block is not the model answering.

    Both sides are stripped, so a response that gained only a tool fence after
    the snapshot is still a stall. The first version of the sibling guard sat
    before `strip_tool_blocks` and never fired for exactly this reason.
    """
    after = PROMISE + '\n\n[TOOL_CALL]{"name": "web_fetch", "arguments": {}}[/TOOL_CALL]'
    assert _text_is_only_preamble(after, PROMISE) is True


def test_whitespace_after_the_tools_is_still_a_stall():
    assert _text_is_only_preamble(PROMISE + "\n\n   \n\t", PROMISE) is True


def test_no_tool_ran_means_no_stall_verdict():
    # Nothing to compare against — a plain conversational turn is not a stall.
    assert _text_is_only_preamble("Here's the answer.", None) is False


# --- what the user is told ----------------------------------------------------

def test_turn3_tools_produce_a_notice():
    notice = _gathering_only_notice(TURN3_TOOLS)
    assert notice, "web_search + web_fetch is a read-only turn and must be reported"
    assert "`web_search`" in notice and "`web_fetch`" in notice
    assert "nothing was created or changed" in notice.lower()
    assert notice.count("`web_fetch`") == 1, "each tool named once, not per call"


def test_notice_is_appended_to_the_promise_not_substituted():
    """The model keeps its voice; the user gets the correction underneath."""
    notice = _gathering_only_notice(TURN3_TOOLS)
    combined = PROMISE.strip() + "\n\n" + notice
    assert combined.startswith(PROMISE)
    assert notice in combined


def test_an_effectful_turn_is_never_called_a_stall():
    # If edit_document ran, the turn changed something — silence is item 7's
    # problem (report it), not item 8's (nothing happened).
    assert _gathering_only_notice(TURN3_TOOLS + [{"tool": "edit_document"}]) == ""


# --- the active half was reverted ------------------------------------------

def test_the_active_half_stayed_reverted():
    """The "push one more round" half was tried and withdrawn — see run 8c80cf8d.

    Told to *"finish the job NOW using the appropriate tool"*, the model called
    `update_document` with empty content and destroyed a 6186-character
    document. Reporting a stall is safe; commanding an idle model to act is not.
    Full account in tests/test_document_tools_reject_empty_writes.py.
    """
    assert "_stall_nudge_count += 1" not in AGENT_LOOP_SRC
    assert "REVERTED 2026-07-19" in AGENT_LOOP_SRC, (
        "the reason must stay at the code site so this isn't retried blind"
    )


def test_snapshot_is_taken_before_every_tool_not_just_document_tools():
    # Run 4e217ae0 turn 3 used only web_search/web_fetch. A doc-tool-only
    # snapshot would never have seen it.
    assert "_text_before_last_tool = full_response" in AGENT_LOOP_SRC
    snap_at = AGENT_LOOP_SRC.index("_text_before_last_tool = full_response")
    doc_gate_at = AGENT_LOOP_SRC.index("if block.tool_type in DOC_TOOLS and not result.get(\"error\")")
    assert snap_at < doc_gate_at, "snapshot must be taken for every tool block"


