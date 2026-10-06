"""The closing summary must report the whole turn, and must not mistake a
preamble for a report — notes/todo.md item 7.

Two defects, both observed in production:

**Under-reporting.** ``_ody_doc_tool_info`` was REPLACED by each successful
document tool, so a turn with several edit rounds reported only the last.
Run baac5d34 applied 5+1+3+1 = 10 edits across four calls and told the user
"1 edit applied, 1 not applied" — under-reporting tenfold, and reading as a
near-total failure when most of the work had landed.

**Silence.** ``_closing_doc_summary`` only fired when the response was empty,
on the assumption that non-empty meant the model had summarised. It doesn't:
qwen3.5:9b habitually opens with its intent — *"I'll fact-check the guide by
searching for verified data…"* — before calling any tool. Run 4e217ae0 turn 2
applied four edits and reported none of them, because that preamble made the
response non-empty. The user, told nothing had happened, asked again 16 seconds
later; the repeat turn spent 162s and produced nothing at all.

The preamble test is positional, not lexical — text written before the tool ran
cannot describe what the tool did, whatever language it is in.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agent_loop import (  # noqa: E402
    _closing_doc_summary,
    _doc_tool_summary,
    _text_is_only_preamble,
)


def _accumulate(prev, **result):
    """Mirror of the accumulation the agent loop performs per successful call."""
    def _sum(a, b):
        if a is None and b is None:
            return None
        return (a or 0) + (b or 0)

    return {
        "tool": result.get("tool", "edit_document"),
        "title": result.get("title") or prev.get("title") or "",
        "version": result.get("version"),
        "applied": _sum(prev.get("applied"), result.get("applied")),
        "skipped": _sum(prev.get("skipped"), result.get("skipped")),
        "stale_values": result.get("stale_values") or [],
        "calls": (prev.get("calls") or 0) + 1,
    }


# --- under-reporting -----------------------------------------------------------

def test_baac5d34_reports_all_ten_edits_not_just_the_last():
    """The exact run from the TODO: 5+1+3+1 edits across four calls."""
    info = {}
    for applied, skipped, ver in ((5, 0, 2), (1, 0, 4), (3, 0, 5), (1, 1, 7)):
        info = _accumulate(info, applied=applied, skipped=skipped, version=ver,
                           title="Pink Oyster Mushroom Growth Phases")

    assert info["applied"] == 10
    assert info["skipped"] == 1
    assert info["version"] == 7, "the version must be the latest, not a sum"
    assert info["calls"] == 4

    line = _doc_tool_summary(info)
    assert "10 edits applied" in line
    assert "across 4 rounds" in line
    assert "1 not applied" in line
    assert "(v7)" in line


def test_a_single_call_turn_reads_unchanged():
    info = _accumulate({}, applied=3, skipped=0, version=2, title="Guide")
    line = _doc_tool_summary(info)
    assert "3 edits applied" in line
    assert "rounds" not in line, "no round count for a single-call turn"


def test_stale_values_take_the_latest_not_the_union():
    """stale_values lints the document as it now stands; earlier entries may
    since have been fixed, so accumulating them would report phantom problems."""
    info = _accumulate({}, applied=2, version=2, stale_values=["20-30°C", "3-7 days"])
    info = _accumulate(info, applied=2, version=3, stale_values=["3-7 days"])
    assert info["stale_values"] == ["3-7 days"]
    assert info["applied"] == 4


# --- preamble vs report --------------------------------------------------------

PREAMBLE = ("I'll fact-check the pink oyster mushroom guide by searching for "
            "verified mycological data on *Pleurotus djamor* growth phases.")


def test_preamble_is_not_mistaken_for_a_report():
    # Nothing was written after the edit landed, so the whole response predates it.
    assert _text_is_only_preamble(PREAMBLE, PREAMBLE) is True


def test_text_written_after_the_edit_counts_as_a_report():
    after = PREAMBLE + "\n\nI corrected the fruiting temperature and the CO2 range."
    assert _text_is_only_preamble(after, PREAMBLE) is False


def test_trailing_whitespace_alone_is_still_only_a_preamble():
    assert _text_is_only_preamble(PREAMBLE + "\n\n  \n", PREAMBLE) is True


def test_no_document_tool_ran_means_no_preamble_verdict():
    assert _text_is_only_preamble("some text", None) is False


def test_empty_prior_text_is_not_a_preamble():
    # The model wrote nothing before the tool; whatever it says now is a report.
    assert _text_is_only_preamble("I updated the doc.", "") is False


# --- the two paths together ----------------------------------------------------

def test_4e217ae0_turn2_appends_the_report_to_the_preamble():
    """Four edits landed and the user was told nothing. Now they are told, and
    the model keeps its own opening line."""
    info = _accumulate({}, applied=4, skipped=0, version=2,
                       title="Pink Oyster Mushroom Growth Phases - Pleurotus djamor Guide")
    final, chunk = _closing_doc_summary(PREAMBLE, info, preamble_only=True)

    assert chunk is not None, "a preamble-only turn must still report"
    assert final.startswith(PREAMBLE), "the model's own words are kept"
    assert "4 edits applied" in final
    assert "(v2)" in final
    assert chunk.startswith("data: "), "must be a streamable SSE chunk"


def test_a_real_summary_is_left_alone():
    info = _accumulate({}, applied=4, version=2, title="Guide")
    own = "I corrected four values: fruiting temperature, CO2, humidity and timeline."
    final, chunk = _closing_doc_summary(own, info, preamble_only=False)
    assert final == own
    assert chunk is None


def test_empty_response_still_gets_a_bare_summary():
    info = _accumulate({}, applied=4, version=2, title="Guide")
    final, chunk = _closing_doc_summary("", info, preamble_only=False)
    assert chunk is not None
    assert final.startswith("Updated **Guide** (v2)")
    assert not final.startswith("\n")


def test_no_document_tool_means_no_synthesized_line():
    final, chunk = _closing_doc_summary("", {}, preamble_only=True)
    assert final == ""
    assert chunk is None


@pytest.mark.parametrize("preamble_only", [True, False])
def test_summary_never_duplicates_itself(preamble_only):
    """Appending must not run twice over an already-reported turn."""
    info = _accumulate({}, applied=4, version=2, title="Guide")
    once, _ = _closing_doc_summary(PREAMBLE, info, preamble_only=preamble_only)
    twice, chunk = _closing_doc_summary(once, info, preamble_only=False)
    assert twice == once
    assert chunk is None
