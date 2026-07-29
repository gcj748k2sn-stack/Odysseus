"""The save path must not reclassify answer text as reasoning — docs/todo.md item 6.

`_normalize_thinking` exists to move *inline* reasoning into the thinking panel
for models that emit it untagged. Its fallbacks chose the split point by
position — "everything above the last plausible line is reasoning" — which is a
guess, not evidence, and it was wrong on two recorded runs.

Both fixtures below are the real `round_texts[0]` from `app.db`, paired with the
message content that was actually saved, so the assertions are against observed
loss rather than a constructed example:

  run_f14a8f52_clarifying_questions  300 chars -> 79 saved. A numbered list of
                                     clarifying questions; question 1 was
                                     deleted and the user's reply began "2.".
  run_c7da3649_factcheck_findings    705 chars -> 28 saved. A fact-check naming
                                     three real errors, reduced to "Let me
                                     correct these issues:" — the dangling
                                     promise of item 8, manufactured here.

**The negative controls are the point of this file**, in the same way the clean
run is the point of `test_document_fidelity.py`. A "fix" that made
`_normalize_thinking` return its input unchanged would satisfy every loss
assertion below and quietly delete the feature; `test_genuine_*` is what stops
that. See item 19's `isabs` guard, which was False in the broken and the fixed
case alike.
"""
import pathlib

import pytest

from routes.chat_helpers import (
    _normalize_thinking,
    _reasoning_split_is_safe,
    clean_thinking_for_save,
)

FIX = pathlib.Path(__file__).parent / "fixtures" / "normalize_thinking"

RECORDED = [
    "run_f14a8f52_clarifying_questions",
    "run_c7da3649_factcheck_findings",
]


def _recorded(name):
    return (
        (FIX / f"{name}.round_text.txt").read_text(),
        (FIX / f"{name}.saved_content.txt").read_text(),
    )


# ── the recorded losses ──────────────────────────────────────────────────────

@pytest.mark.parametrize("name", RECORDED)
def test_recorded_run_keeps_every_word_the_model_wrote(name):
    """Nothing the model emitted may be missing from the saved message."""
    text, _ = _recorded(name)
    reply, md = clean_thinking_for_save(text)
    assert reply.strip() == text.strip()
    assert not md.get("thinking")


@pytest.mark.parametrize("name", RECORDED)
def test_recorded_run_is_no_longer_split(name):
    text, _ = _recorded(name)
    assert _normalize_thinking(text) == text


def test_the_deleted_clarifying_question_survives():
    """Pin the specific sentence the user never saw, not just the length.

    A length assertion passes if the text is preserved but reordered or
    re-wrapped. This is the question that went missing.
    """
    text, saved = _recorded("run_f14a8f52_clarifying_questions")
    assert "1. **Where is the existing HTML" in text
    assert "1. **Where is the existing HTML" not in saved, (
        "fixture no longer reproduces the loss it was captured for"
    )
    reply, _ = clean_thinking_for_save(text)
    assert "1. **Where is the existing HTML" in reply


def test_the_factcheck_findings_survive():
    text, saved = _recorded("run_c7da3649_factcheck_findings")
    assert saved.strip() == "Let me correct these issues:"
    reply, _ = clean_thinking_for_save(text)
    for finding in (
        "Nutritional profile is incorrect",
        "Pinning timeline confusion",
        "Temperature range could be more specific",
    ):
        assert finding in reply


# ── negative controls: the feature still works ───────────────────────────────

def test_genuine_gemma_inline_reasoning_is_still_extracted():
    text = (
        "The user is greeting me and wants a friendly reply. "
        "I should keep it short and warm.\n"
        "Hey! Good to hear from you — what are you working on?"
    )
    reply, md = clean_thinking_for_save(text)
    assert md["thinking"].startswith("The user is greeting me")
    assert reply == "Hey! Good to hear from you — what are you working on?"


def test_genuine_thinking_process_prefix_is_still_extracted():
    text = (
        "Thinking Process: they want the capital of France. That is Paris. "
        "Keep the answer to one line.\n\n"
        "The capital of France is Paris."
    )
    reply, md = clean_thinking_for_save(text)
    assert "capital of France is Paris" in reply
    assert "Thinking Process" not in reply
    assert md["thinking"]


def test_explicit_think_tags_are_still_extracted():
    text = "<think>I need to check the docs first.</think>\nAll set — the service is running."
    reply, md = clean_thinking_for_save(text)
    assert reply == "All set — the service is running."
    assert md["thinking"] == "I need to check the docs first."


# ── the guard itself ─────────────────────────────────────────────────────────

def test_guard_refuses_a_reply_that_is_only_a_lead_in():
    assert not _reasoning_split_is_safe("I looked at the file.", "Let me correct these issues:")


def test_guard_refuses_when_the_discarded_half_is_authored_output():
    assert not _reasoning_split_is_safe("I found problems:\n\n1. the first\n2. the second", "and that is all")
    assert not _reasoning_split_is_safe("## Findings\n\nsomething here", "and that is all")


def test_guard_refuses_an_empty_half():
    assert not _reasoning_split_is_safe("", "a reply")
    assert not _reasoning_split_is_safe("some reasoning", "   ")


def test_guard_allows_plain_prose_reasoning():
    assert _reasoning_split_is_safe(
        "The user wants a greeting. I should keep it warm and short.",
        "Hey! What are you working on?",
    )


# ── a property, so a future fallback inherits the rule ───────────────────────

@pytest.mark.parametrize("name", RECORDED)
def test_no_split_ever_discards_a_numbered_list_item(name):
    """Whatever branch fires, a list item may not vanish from the message."""
    text, _ = _recorded(name)
    reply, _ = clean_thinking_for_save(text)
    for marker in ("1.", "2."):
        if any(line.strip().startswith(marker) for line in text.split("\n")):
            assert any(line.strip().startswith(marker) for line in reply.split("\n")), (
                f"list item {marker} was dropped from the saved message"
            )
