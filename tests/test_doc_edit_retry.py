"""Retry and end-of-turn guard for failed document edits.

Run b5fe4ef5 (2026-07-18): `edit_document` failed, the model got a generic
parse error, re-emitted the same broken call, and quit. 526 seconds, no
version written, and because the turn had tool events the empty-response guard
let `routes/chat_routes.py` save a bare "Done." — the shape of a completed
correction for a document that was never touched.

Two halves, tested here:
  - the corrective directive attached to the failed tool result, which
    escalates to a full `update_document` rewrite on the second failure;
  - the end-of-turn guard, which refuses to let a turn whose last document
    edit failed report success. Guidance can't be enforced; this can.
"""

import json

from src.agent_loop import (
    DOC_EDIT_RETRY_TOOLS,
    _doc_edit_retry_directive,
    _empty_response_fallback,
)


def _delta(chunk):
    assert chunk.startswith("data: ")
    return json.loads(chunk[len("data: "):])["delta"]


def test_first_failure_asks_for_a_targeted_retry():
    d = _doc_edit_retry_directive("edit_document", 1)
    assert "DID NOT HAPPEN" in d
    assert "```edit_document" in d
    assert "<<<FIND>>>" in d and "<<<REPLACE>>>" in d and "<<<END>>>" in d
    # It must not suggest the rewrite yet — a targeted edit is still preferable.
    assert "update_document" not in d


def test_second_failure_escalates_to_a_full_rewrite():
    """The point of escalating: update_document has no FIND text to mismatch."""
    d = _doc_edit_retry_directive("edit_document", 2)
    assert "```update_document" in d
    assert "failed 2 times" in d
    assert "<<<FIND>>>" not in d


def test_directive_never_reads_as_success():
    for attempt in (1, 2, 5):
        d = _doc_edit_retry_directive("edit_document", attempt)
        assert "UNCHANGED" in d.upper()
        assert "do not end the turn" in d.lower()


def test_all_three_document_tools_are_covered():
    assert set(DOC_EDIT_RETRY_TOOLS) == {
        "edit_document", "suggest_document", "update_document"
    }


def test_empty_turn_after_failed_edit_reports_failure_not_done():
    """The b5fe4ef5 shape: tool events present, no text, edit failed.

    The old guard returned early on `tool_events` alone, so this turn reached
    chat_routes and was saved as "Done.".
    """
    events = [{"round": 2, "tool": "edit_document", "command": "",
               "output": "No valid <<<FIND>>> blocks found"}]
    response, chunk = _empty_response_fallback(
        "", "", events,
        doc_edit_failures=1,
        doc_edit_error="edit_document received no content",
    )
    assert "document is unchanged" in response.lower()
    assert "edit_document received no content" in response
    assert chunk is not None and _delta(chunk) == response


def test_success_claim_after_failed_edit_is_contradicted():
    """The worse case: the model says it corrected the document. It didn't.

    The failure count only survives to the guard if the LAST document tool
    errored, so prose here is a false success claim.
    """
    events = [{"round": 2, "tool": "edit_document", "output": "error"}]
    response, chunk = _empty_response_fallback(
        "I've corrected the temperature ranges.", "", events,
        doc_edit_failures=2,
        doc_edit_error="No valid <<<FIND>>> blocks found",
    )
    assert response.startswith("I've corrected the temperature ranges.")
    assert "document is unchanged" in response.lower()
    assert "2 attempts" in response
    # Only the appended notice is streamed — the prose was already sent.
    assert _delta(chunk).strip().startswith("I couldn't apply the edit")


def test_recovered_turn_is_left_alone():
    """A failure followed by a success resets the count — not a failed turn."""
    events = [{"round": 3, "tool": "edit_document", "output": "Document edited: v3"}]
    response, chunk = _empty_response_fallback(
        "Updated the document — 4 edits applied.", "", events, doc_edit_failures=0
    )
    assert response == "Updated the document — 4 edits applied."
    assert chunk is None


def test_unrelated_empty_response_guard_still_works():
    """Pre-existing behaviour must not regress."""
    assert _empty_response_fallback("answer", "", [])[1] is None
    assert _empty_response_fallback("", "", [{"tool": "bash"}])[1] is None
    assert _empty_response_fallback("", "reasoning only", [])[0] == "reasoning only"
    empty_response, empty_chunk = _empty_response_fallback("", "", [])
    assert "empty response" in empty_response
    assert empty_chunk is not None
