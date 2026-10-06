"""Prompt rules the model is supposed to follow must actually be in the prompt.

`src/agent_loop.py` assigns `_AGENT_RULES` **twice** — a 116-line block at ~660
and an 851-character "## Base rules" block at ~776. Python keeps the second, so
the first has never reached a model. Nothing failed; the module imports, the
suite is green, and the rules read as live to anyone grepping the file.

That is the notes/todo.md item 16 shape — *a green suite asserting a property
nothing enforces* — applied to the system prompt. It matters because open items
were being reasoned about as if those rules were in force:

    "BIAS TOWARD ACTION on edit requests … JUST DO IT"  → dead, while run
        fd0f9ba0 refused to create a document three times.
    "AFTER A TOOL SUCCEEDS … no validation theater"     → dead, while item 12
        records the model still re-verifying what it just created.
    "YOU DECLARE WHEN THE JOB IS DONE … the only wrong
        moves are trailing off mid-task"               → dead, and item 8 is
        exactly trailing off mid-task.

**Weaker equivalents of some of them do survive** in the live "## Base rules"
(*"After a tool succeeds, do not second-guess it"*), so this is not "no rules
reach the model" — it is "the emphatic versions someone wrote after watching a
failure do not". Don't over-claim it in either direction.

The tests below assert against the *assembled* prompt, never the source text, so
a rule that gets moved between sections still passes and a rule that gets
shadowed by a second assignment fails.
"""
import pytest

from src.agent_loop import AGENT_SYSTEM_PROMPT


@pytest.fixture(scope="module")
def prompt():
    return AGENT_SYSTEM_PROMPT


# ── the rules added 2026-07-28, each from an observed failure ────────────────

def test_an_existing_document_is_not_a_reason_to_refuse(prompt):
    """Run fd0f9ba0: three identical requests, no document, because one was
    already open and the model kept explaining it instead of creating."""
    assert "is not a reason to refuse" in prompt


def test_titles_may_not_carry_unchecked_claims(prompt):
    """42889f7b titled a cached reading "(Live Fetch)" while its own body said
    "cached ~77 seconds ago". Two other documents titled themselves "Fact
    Checked & Corrected" while carrying another species' temperatures."""
    assert 'Do not label a document "Fact Checked"' in prompt
    assert "trusts most and checks least" in prompt


def test_figures_must_be_attributed_or_marked_unverified(prompt):
    assert "Say where a number came from" in prompt
    assert "marked as unverified" in prompt


def test_cached_data_may_not_be_reported_as_current(prompt):
    """Item 17's original failure: the model read a cached `uptime: 91 s` and
    reported it as a live measurement."""
    assert "is not a current reading" in prompt


def test_ambiguous_names_must_be_disambiguated_in_queries(prompt):
    """Item 14: "Pink (singer) — Wikipedia" came back as a top result for a
    pink-oyster cultivation query, and nothing downstream noticed."""
    assert "also a common word" in prompt


def test_a_search_is_not_a_verdict(prompt):
    """The measured finding behind item 2b, stated to the model.

    Asked for "fact checked infos" and given four source fetches, the model
    produced the *worst* document of six; the plain unresearched run produced
    the best. Retrieval is not neutral here, so the rule is about admitting
    non-verification rather than about searching more.
    """
    assert "A search is not a verdict" in prompt


# ── the shadowing that made this file necessary ──────────────────────────────

DEAD_BLOCK_MARKERS = [
    "validation theater",
    "BIAS TOWARD ACTION",
    "YOU DECLARE WHEN THE JOB IS DONE",
    "DO NOT GO SILENT",
]


@pytest.mark.parametrize("marker", DEAD_BLOCK_MARKERS)
def test_shadowed_rules_are_documented_as_absent(marker, prompt):
    """Pins the current, surprising truth rather than the intended one.

    These four live only in the shadowed `_AGENT_RULES` block and reach no
    model. **If one of these starts passing, that is good news** — someone
    revived the block — but it must be a deliberate act with the prompt-size
    cost understood, not a silent merge. Update this test in the same commit.
    """
    assert marker not in prompt


def test_the_surviving_weaker_equivalents_are_present(prompt):
    """So "the rules are dead" is never read as "there are no rules"."""
    assert "do not second-guess it" in prompt
    assert "After a tool fails" in prompt


def test_the_document_and_web_sections_are_assembled_at_all(prompt):
    """A section that stops being included would make every assertion above
    fail for an unrelated reason; name that cause explicitly."""
    assert "## Document rules" in prompt
    assert "## Web rules" in prompt
