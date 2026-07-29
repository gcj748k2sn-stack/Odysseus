"""The ⚠️ blocks must reach the user even when the model wrote its own summary.

docs/todo.md item 21. Three S1 checks ride in `_doc_tool_summary` — item 3's
`stale_values`, 2a's `fidelity`, 2b's `known_facts` — and **both** callers used
to discard the entire string whenever the model had written prose after the tool
ran. The reasoning was sound and the conclusion was wrong: the user had been
told what happened, but not that it was wrong.

Run eb2d0ac1, 2026-07-28, is the case this file exists for. The model
researched, fetched two sources, and created an 8,636-character document titled

    Pink Oyster Mushroom (Pleurotus djamor) Growth Phases Guide - Fact Checked 2026-07-28

containing *"Temperature drop of 5 – 10°F"* — a prescribed cold shock on a
thermophilic species, which is the exact failure that retired the 4B. The 2b
checker caught it. The model then wrote a confident closing summary with ✅ ticks
and "Key verified facts", so `_closing_doc_summary` returned early and **the
user saw neither finding**.

**The net was withheld because the model sounded sure**, which is the one case
it exists for. The inverse of the `"Done."` bug: that reported success for work
that never happened; this reported success for work that happened wrongly.
"""
import pytest

from src.agent_loop import _closing_doc_summary, _doc_tool_summary

# Abbreviated from the real run.
EB2D0AC1 = {
    "tool": "create_document",
    "title": "Pink Oyster Mushroom Growth Phases Guide - Fact Checked 2026-07-28",
    "version": 1,
    "known_facts": [
        "“Temperature drop of 5 – 10°F” — P. djamor is thermophilic and needs no cold shock.",
        "`5–10°F` is outside the recorded fruiting range 20–30 °C.",
    ],
}
MODEL_PROSE = (
    "Created the comprehensive Pink Oyster Mushroom Growth Phases Guide! 📄🍄\n\n"
    "The document includes all 5 major growth phases with fact-checked details."
)


# ── the recorded failure ─────────────────────────────────────────────────────

def test_warnings_survive_a_confident_model_summary():
    out, chunk = _closing_doc_summary(MODEL_PROSE, EB2D0AC1, preamble_only=False)
    assert "Contradicts what we already established" in out
    assert "cold shock" in out
    assert chunk is not None, "nothing was streamed to the client"


def test_the_model_keeps_its_own_words():
    """Appended, never replacing. The model's summary is often useful and this
    is a warning, not a correction."""
    out, _ = _closing_doc_summary(MODEL_PROSE, EB2D0AC1, preamble_only=False)
    assert out.startswith(MODEL_PROSE)


def test_the_action_line_is_not_duplicated():
    """The user has already been told a document was created. Saying "Created
    **X** (v1)." underneath the model's own "Created the comprehensive…" reads
    as two separate documents."""
    out, _ = _closing_doc_summary(MODEL_PROSE, EB2D0AC1, preamble_only=False)
    assert "Created **" not in out


@pytest.mark.parametrize("key,needle", [
    ("stale_values", "Still inconsistent"),
    ("fidelity", "Doesn't match the source"),
    ("known_facts", "Contradicts what we already established"),
])
def test_every_warning_class_survives(key, needle):
    """All three ride the same path, so all three had the same hole."""
    info = {"tool": "edit_document", "title": "T", "version": 2, key: ["something"]}
    out, _ = _closing_doc_summary("I've updated the document.", info, preamble_only=False)
    assert needle in out


# ── negative controls ────────────────────────────────────────────────────────

def test_a_clean_turn_appends_nothing():
    """No findings, no noise. If this fails, every document turn grows a tail."""
    info = {"tool": "create_document", "title": "T", "version": 1}
    out, chunk = _closing_doc_summary("Created it, all good.", info, preamble_only=False)
    assert out == "Created it, all good."
    assert chunk is None


def test_a_silent_turn_still_gets_the_full_summary():
    """The original behaviour, unchanged — this is item 7 and it must not
    regress into warnings-only."""
    out, chunk = _closing_doc_summary("", EB2D0AC1, preamble_only=False)
    assert "Created **" in out
    assert "Contradicts what we already established" in out
    assert chunk is not None


def test_a_preamble_still_gets_the_full_summary():
    """Text written *before* the tool ran cannot describe what the tool did, so
    the action line is still needed (item 7's positional rule)."""
    out, _ = _closing_doc_summary("I'll create that document now.", EB2D0AC1, preamble_only=True)
    assert "Created **" in out
    assert "Contradicts what we already established" in out


def test_no_doc_info_changes_nothing():
    assert _closing_doc_summary("hello", {}, preamble_only=False) == ("hello", None)


# ── the split itself ─────────────────────────────────────────────────────────

def test_warnings_only_drops_the_action_line_and_keeps_the_blocks():
    full = _doc_tool_summary(EB2D0AC1)
    only = _doc_tool_summary(EB2D0AC1, warnings_only=True)
    assert full.startswith("Created **")
    assert not only.startswith("Created **")
    assert "Contradicts what we already established" in full
    assert "Contradicts what we already established" in only


def test_warnings_only_is_empty_when_there_is_nothing_to_warn_about():
    info = {"tool": "create_document", "title": "T", "version": 1}
    assert _doc_tool_summary(info, warnings_only=True) == ""
    assert _doc_tool_summary(info) == "Created **T** (v1)."


def test_the_default_rendering_is_byte_identical_to_before_the_split():
    """The action line and warnings were one accumulating string; they are now
    joined parts. Pin the exact output so the refactor stayed cosmetic."""
    info = {
        "tool": "edit_document", "title": "Guide", "version": 5,
        "applied": 7, "calls": 2, "skipped": 4,
        "stale_values": ["90%"],
    }
    assert _doc_tool_summary(info) == (
        "Updated **Guide** (v5) — 7 edits applied across 2 rounds, "
        "**4 not applied** (the FIND text didn't match — those corrections are "
        "still missing).\n\n"
        "⚠️ **Still inconsistent** — `90%` was corrected in one place but still "
        "appears elsewhere in the document. The document now contradicts itself; "
        "ask me to fix the remaining spots."
    )
