"""Odysseus's own end-of-turn notices must not reach the model as its words.

The guards in `src/turn_report.py` and `src/agent_loop.py` append notices to the saved reply when a
turn fails or stops early. They are written for the person reading the
transcript — "the tool results above are real", "Ask me to continue…" — and
`Session.get_context_messages` used to replay them to the model verbatim.
Measured 2026-10-04 over 268 recorded replies: 56 carried a notice, 48 were
followed by more turns, and after a notice "continue" carried the work on in
0 of 6 cases (the tool results were never kept for the model).

Every notice the agent loop can still write is built through the REAL function,
so a wording change in `turn_report.py` / `agent_loop.py` that the patterns in `src/ui_notices.py`
no longer match fails here instead of leaking silently. The stream-failure
notice is no longer written (upstream's `[Agent stopped: …]` replaced it in the
2026-10-06 merge), but chats saved before then carry it, so its last wording is
frozen below as saved text. The negative controls are the other half:
a stripper that also ate ordinary replies would pass a positive-only suite.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest  # noqa: E402

from core.models import ChatMessage, Session  # noqa: E402
from src.agent_loop import _empty_response_fallback  # noqa: E402
from src.turn_report import (  # noqa: E402
    _gathering_only_notice,
    _tool_payload_as_text_notice,
    _unstarted_promise_notice,
)
from src.ui_notices import (  # noqa: E402
    INCOMPLETE_TURN_MARKER,
    context_view_of_reply,
    strip_ui_notices,
)

# Verbatim output of the removed `_stream_failure_notice`, as stored in chats
# saved before the 2026-10-06 merge.
_SAVED_STREAM_FAILED_NO_TOOLS = (
    "⚠️ **The request to the model failed after 0s — `Cannot reach "
    "http://localhost:1234 (503)`.** Anything above is the part that arrived "
    "before it did; the turn did not finish, so treat it as incomplete rather "
    "than as an answer."
)
_SAVED_STREAM_FAILED_WITH_TOOLS = (
    "⚠️ **The request to the model failed after 0s — `{\"status\": 400, "
    "\"text\": \"request (17539 tokens) exceeds `ctx`\"}` (+1 more).** Work "
    "completed before it failed has been kept — the tool results above are "
    "real. What is missing is whatever the model would have done next, so the "
    "task may be half-finished."
)
_SAVED_STREAM_FAILED_NO_ELAPSED = (
    "⚠️ **The request to the model failed — `boom`.** Anything above is the "
    "part that arrived before it did; the turn did not finish, so treat it as "
    "incomplete rather than as an answer."
)

_EDIT_PAYLOAD = (
    "I'll fix it:\n\n```json\n"
    '{"edits": [{"find": "old", "replace": "new"}]}\n'
    "```"
)


def _real_notices():
    """(label, notice text) for every template, built by the real functions."""
    empty, _ = _empty_response_fallback("", "", [])
    yield "empty_response", empty
    yield "saved_stream_failed_no_tools", _SAVED_STREAM_FAILED_NO_TOOLS
    yield "saved_stream_failed_with_tools", _SAVED_STREAM_FAILED_WITH_TOOLS
    yield "saved_stream_failed_no_elapsed", _SAVED_STREAM_FAILED_NO_ELAPSED
    yield "gathering_one_tool", _gathering_only_notice([{"tool": "web_search"}])
    yield "gathering_two_tools", _gathering_only_notice(
        [{"tool": "web_search"}, {"tool": "web_fetch"}]
    )
    yield "unstarted_promise", _unstarted_promise_notice("I'll create the document now:", [])
    yield "payload_as_text", _tool_payload_as_text_notice(_EDIT_PAYLOAD, [])


@pytest.mark.parametrize("label,notice", list(_real_notices()))
def test_every_real_notice_strips_completely(label, notice):
    assert notice.strip(), f"{label}: the real function produced no notice — fixture is stale"
    assert strip_ui_notices(notice) == "", label
    assert context_view_of_reply(notice) == INCOMPLETE_TURN_MARKER, label


@pytest.mark.parametrize("label,notice", list(_real_notices()))
def test_model_text_before_a_notice_survives(label, notice):
    reply = "I'll search for the growth phases first." + "\n\n" + notice.lstrip()
    view = context_view_of_reply(reply)
    assert view == "I'll search for the growth phases first.\n\n" + INCOMPLETE_TURN_MARKER, label


def test_stacked_notices_all_strip():
    # The empty-response text and a stream failure arrive together on a dead endpoint.
    empty, _ = _empty_response_fallback("", "", [])
    failed = _SAVED_STREAM_FAILED_NO_TOOLS
    assert context_view_of_reply(empty + "\n\n" + failed) == INCOMPLETE_TURN_MARKER


def test_old_gathering_tail_in_saved_chats_still_strips():
    # Every chat saved before 2026-10-04 carries the old promise.
    old = (
        "I ran `web_search`, `web_fetch` and then stopped without producing an answer — "
        "**nothing was created or changed.** The information was gathered but never used. "
        "Ask me to continue and I'll carry on from there."
    )
    assert strip_ui_notices(old) == ""


def test_gathering_notice_no_longer_promises_continue():
    notice = _gathering_only_notice([{"tool": "web_search"}])
    assert "continue" not in notice.lower()
    assert "nothing was created or changed" in notice.lower()


# ── negative controls ─────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "Here is the recipe: 225 g flour, 3 eggs, 500 ml milk.",
    "The request failed earlier, but the second search worked.",
    "I ran `web_search` and found three sources.",
    "⚠️ **Careful:** nothing was created or changed in the file yet.",
    "Ask me to continue and I'll carry on from there.",  # tail alone, no notice head
    "",
])
def test_ordinary_replies_are_byte_identical(text):
    assert strip_ui_notices(text) == text
    assert context_view_of_reply(text) == text


def test_non_string_content_is_untouched():
    multimodal = [{"type": "text", "text": "hi"}]
    assert context_view_of_reply(multimodal) is multimodal


# ── the wiring: Session.get_context_messages ──────────────────────────────

def _session():
    empty, _ = _empty_response_fallback("", "", [])
    gathering = _gathering_only_notice([{"tool": "web_search"}])
    s = Session(id="s1", name="t", endpoint_url="http://x/v1", model="m")
    s.add_message(ChatMessage("user", "oh hi mark"))
    s.add_message(ChatMessage("assistant", empty))
    s.add_message(ChatMessage("user", "research parasol mushrooms"))
    s.add_message(ChatMessage("assistant", "I'll search for that.\n\n" + gathering))
    s.add_message(ChatMessage("user", "quoting you: " + gathering))
    s.add_message(ChatMessage("assistant", "Here is the answer."))
    return s


def test_context_view_strips_notices_and_keeps_turn_structure():
    ctx = _session().get_context_messages()
    assert [m["role"] for m in ctx] == ["user", "assistant"] * 3
    assert ctx[1]["content"] == INCOMPLETE_TURN_MARKER
    assert ctx[3]["content"] == "I'll search for that.\n\n" + INCOMPLETE_TURN_MARKER
    assert ctx[5]["content"] == "Here is the answer."


def test_user_messages_are_never_rewritten():
    ctx = _session().get_context_messages()
    assert "stopped without producing an answer" in ctx[4]["content"]


def test_raw_history_keeps_notices_for_display():
    s = _session()
    s.get_context_messages()
    assert "empty response" in s.history[1].content
    assert "stopped without producing an answer" in s.history[3].content


# ── Upstream's terminal-failure note (merged 2026-10-06) ──
# After the merge a provider/stream failure ends the turn with
# "[Agent stopped: …]" (src/agent_loop.py, routes/chat_routes.py) instead of
# the fork's old stream-failure notice, so that note has to strip the same way.

def test_upstream_agent_stopped_note_strips_to_the_marker():
    reply = "Here is what I found so far.\n\n[Agent stopped: Model request failed (HTTP 504)]"
    assert context_view_of_reply(reply) == (
        "Here is what I found so far.\n\n" + INCOMPLETE_TURN_MARKER
    )
    assert context_view_of_reply("[Agent stopped: Model request failed]") == INCOMPLETE_TURN_MARKER


def test_agent_stopped_lookalike_in_prose_is_left_alone():
    """Negative control: only the bracketed template matches."""
    text = "The log said Agent stopped: timeout, which is a different thing."
    assert context_view_of_reply(text) == text
