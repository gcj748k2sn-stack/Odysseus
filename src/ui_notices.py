"""Odysseus-written notices inside assistant replies — shown to the user, kept
out of what the model reads back.

Several end-of-turn guards in ``src/agent_loop.py`` append a notice to the
saved reply when a turn fails or stops early (empty response, stream error,
"gathered but never answered", a dangling lead-in, an edit written as text).
They are written for the person reading the transcript: they speak in the
model's voice ("I ran `web_search` and then stopped…"), point at tool cards
the UI renders ("the tool results above are real"), and invite a follow-up
("Ask me to continue…").

Replayed to the model as part of the history they do three kinds of damage
(measured 2026-10-04 over 268 recorded replies, see notes/todo.md *"Odysseus's
own notices are replayed to the model as its words"*):

- the model is told about tool results it cannot see — only reply text is
  kept for it, never the tool output;
- it inherits a promise it cannot keep: after a notice, "continue" carried the
  work on in 0 of 6 recorded cases;
- it reasons about the failures as conversation turns (session 0829a3d2:
  *"Then there's a failure message about model connection"*).

``strip_ui_notices`` removes them from the model's view only. The raw history,
which the UI renders, is untouched — same split as slash-command replies in
``core.models.Session.get_context_messages``.

Each pattern mirrors one template in ``src/agent_loop.py``.
``tests/test_ui_notices_context.py`` builds every notice through the real
function and asserts it strips completely, so a wording change there fails a
test instead of leaking silently. Matching is lexical on purpose (CLAUDE.md
§3): these are fixed templates, not model output.
"""

import re

# What the model sees where notices were removed: one neutral, factual line,
# with no instructions, no promises and nothing that points at UI it cannot
# see. Kept rather than dropped because the fact itself matters — without it
# a reply that stopped on "I'll search for…" reads as if the search happened.
# A reply that was nothing but notices becomes just this line (dropping it
# would leave two user turns in a row, which some chat templates reject).
INCOMPLETE_TURN_MARKER = "(This turn ended without a complete answer.)"

# `_gathering_only_notice` tails — the old one stays matchable because it is
# in every chat saved before 2026-10-04.
_GATHERING_TAIL_OLD = "Ask me to continue and I'll carry on from there."
_GATHERING_TAIL_NEW = (
    "The results were not kept, so send the request again to rerun it."
)

_NOTICE_PATTERNS = [
    # `_empty_response_fallback` (the `_error_msg` literal).
    re.compile(
        re.escape(
            "The model returned an empty response. Please try again or "
            "switch to a different model."
        )
    ),
    # `_stream_failure_notice` — head plus one of its two tails.
    re.compile(
        r"⚠️ \*\*The request to the model failed(?: after \d+s)? — `.*?`"
        r"(?: \(\+\d+ more\))?\.\*\* (?:"
        + re.escape(
            "Work completed before it failed has been kept — the tool "
            "results above are real. What is missing is whatever the model "
            "would have done next, so the task may be half-finished."
        )
        + "|"
        + re.escape(
            "Anything above is the part that arrived before it did; the "
            "turn did not finish, so treat it as incomplete rather than as "
            "an answer."
        )
        + ")",
        re.DOTALL,
    ),
    # `_gathering_only_notice`.
    re.compile(
        r"I ran `[^`\n]+`(?:, `[^`\n]+`)* and then stopped without producing "
        r"an answer — \*\*nothing was created or changed\.\*\* The information "
        r"was gathered but never used\. (?:"
        + re.escape(_GATHERING_TAIL_OLD)
        + "|"
        + re.escape(_GATHERING_TAIL_NEW)
        + ")"
    ),
    # `_unstarted_promise_notice`.
    re.compile(
        re.escape(
            "…and then I stopped there — **nothing was created or changed, "
            "and I called no tools this turn.** That sentence was the setup, "
            "not the work. Ask me again and I'll do it."
        )
    ),
    # Upstream's terminal-failure note (merged 2026-10-06): since upstream
    # #5953-era agent_loop changes, a provider/stream failure ends the turn
    # with `[Agent stopped: <reason>]` (agent_loop.py and chat_routes.py,
    # grep "Agent stopped:") instead of reaching `_stream_failure_notice`.
    # Same class of Odysseus-written text, so the model gets the same neutral
    # marker instead of the bracketed note.
    re.compile(r"\[Agent stopped: [^\]\n]{1,300}\]"),
    # `_tool_payload_as_text_notice`.
    re.compile(
        re.escape(
            "⚠️ **I wrote that edit out as text instead of running it — "
            "nothing was created or changed.** A fenced block only executes "
            "when its tag is the tool name (```edit_document); any other tag "
            "is display text. Ask me to try again and I'll make the call "
            "properly."
        )
    ),
]


def strip_ui_notices(text: str) -> str:
    """Return ``text`` without Odysseus's end-of-turn notices.

    Non-string content (multimodal lists) is returned unchanged. Text that
    contains no notice comes back byte-identical, so ordinary replies and the
    KV-cache prefix they form are unaffected.
    """
    if not isinstance(text, str) or not text:
        return text
    out = text
    for pat in _NOTICE_PATTERNS:
        out = pat.sub("", out)
    if out == text:
        return text
    # The guards join notices with "\n\n" or a single space; collapse what is
    # left behind rather than leaving gaps in the replayed reply.
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def context_view_of_reply(text):
    """The model's view of a saved assistant reply.

    Notices are removed and replaced by ``INCOMPLETE_TURN_MARKER`` — appended
    after whatever the model itself wrote, or on its own when nothing else is
    left. A reply without notices comes back unchanged.
    """
    stripped = strip_ui_notices(text)
    if stripped is text or stripped == text:
        return text
    if stripped:
        return f"{stripped}\n\n{INCOMPLETE_TURN_MARKER}"
    return INCOMPLETE_TURN_MARKER
