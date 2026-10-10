"""A turn that says it did something and called no tool gets a notice.

notes/todo.md, *"A turn that claims an action and called no tool is saved as if
it happened"*: session 0ca639d6 (2026-10-07) replied *Created "Switch check"
document* with zero tool calls; no such document exists. No guard fired - the
other zero-tool notices need a trailing colon or a fenced tool payload.

Report-only: the notice states a fact (no tool ran), never makes the model act.

Corpus at build time (app.db copy, assistant rows since 2026-07-28): 94
zero-tool replies, 2 flagged - 0ca639d6 and ae223b4c, both claims of work that
never ran - and 0 of the other 92.
"""

import json

import pytest

from src.turn_report import (
    ACTION_CLAIM_NOTICE,
    _action_claim_notice,
    _claims_action,
    end_of_turn_report,
)
from src.ui_notices import INCOMPLETE_TURN_MARKER, context_view_of_reply

# The exact reply, from app.db.
SWITCH_CHECK = 'Created **"Switch check"** document with the text "hello".'


def _report(text, tool_events=()):
    return end_of_turn_report(
        text, list(tool_events),
        doc_info={}, doc_text_before_tool=None, text_before_last_tool=None,
    )


# --- fires ------------------------------------------------------------------

def test_the_live_reply_gets_the_notice():
    assert _action_claim_notice(SWITCH_CHECK, []) == ACTION_CLAIM_NOTICE


@pytest.mark.parametrize("text", [
    SWITCH_CHECK,
    "I've updated the note with the new humidity range.",
    "I have created the document.",
    "Done! Sent the email to Anna.",
    "✅ Saved to memory: you prefer metric units.",
    "- **Created** the document *Day pack*.",
    "Here you go. Added the event to your calendar for Monday.",
    "Your event has been scheduled for Monday at 9.",
    "The document has been successfully updated.",
    "I just wrote the file `notes.txt`.",
])
def test_claims_of_finished_actions_are_found(text):
    assert _claims_action(text), text


# --- stays silent -----------------------------------------------------------

@pytest.mark.parametrize("text", [
    "You created the document yesterday.",
    "To create a document, ask me and I'll call create_document.",
    '> Created "X" document',
    "If I created a file there, it would be in /tmp.",
    "I created the document earlier in this chat; it is still open.",
    "Previously I updated the note, so it has the new values.",
    "Added milk to the list:\n- milk\n- eggs",
    "```\nCreated document 'X'\n```\nThat is what the log line looks like.",
    "The file was created in 2019.",
    "Here is the updated version of the note:\n\nCO2 below 900 ppm.",
    "Updated pricing: the ESP32 costs about 5 EUR.",
    "Which document should I update?",
    "I can create the document if you want.",
    "Sent. Received. Delivered. Those are the three states.",
    "",
])
def test_ordinary_replies_get_nothing(text):
    assert _claims_action(text) == "", text
    assert _action_claim_notice(text, []) == ""


def test_a_turn_that_ran_a_tool_gets_nothing():
    assert _action_claim_notice(SWITCH_CHECK, [{"tool": "create_document"}]) == ""


# --- end_of_turn_report -----------------------------------------------------

def test_end_of_turn_report_appends_and_streams_the_notice():
    full, chunks = _report(SWITCH_CHECK)
    assert full == SWITCH_CHECK + ACTION_CLAIM_NOTICE
    assert chunks == ["data: " + json.dumps({"delta": ACTION_CLAIM_NOTICE}) + "\n\n"]


def test_end_of_turn_report_leaves_a_tool_turn_alone():
    full, chunks = _report(SWITCH_CHECK, [{"tool": "create_document", "result": {"ok": True}}])
    assert ACTION_CLAIM_NOTICE not in full
    assert all(ACTION_CLAIM_NOTICE not in c for c in chunks)


def test_one_zero_tool_notice_per_turn_payload_first():
    text = (
        "Updated the document.\n\n```json\n"
        '{"edits": [{"find": "old", "replace": "new"}]}\n```'
    )
    full, chunks = _report(text)
    assert "wrote that edit out as text" in full
    assert ACTION_CLAIM_NOTICE not in full
    assert len(chunks) == 1


def test_one_zero_tool_notice_per_turn_promise_first():
    full, chunks = _report("Created the document with these sections:")
    assert "That sentence was the setup" in full
    assert ACTION_CLAIM_NOTICE not in full
    assert len(chunks) == 1


def test_the_model_never_reads_the_notice_back():
    # Replayed, the claim is followed by the neutral marker, not by our notice.
    full, _ = _report(SWITCH_CHECK)
    assert context_view_of_reply(full) == f"{SWITCH_CHECK}\n\n{INCOMPLETE_TURN_MARKER}"
