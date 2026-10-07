"""Odysseus-written notices inside assistant replies: shown to the user, kept out
of what the model reads back.

End-of-turn guards (src/turn_report.py, src/agent_loop.py) append notices to
the saved reply when a turn fails or stops early. They are written for the
person reading the transcript - in the model's voice, pointing at tool cards,
inviting a follow-up. Replayed to the model they mislead it: it is told about
tool results it cannot see, inherits promises it cannot keep, and reasons about
failures as conversation (notes: "Odysseus's own notices are replayed to the
model as its words").

strip_ui_notices removes them from the model's view only; the raw history the
UI renders is untouched (same split as slash-command replies in
core.models.Session.get_context_messages).

Each pattern mirrors one template; tests/test_ui_notices_context.py builds
every live notice through the real function, so a wording change fails a test
instead of leaking. Lexical on purpose: these are fixed templates, not model
output.
"""

import re

# What the model sees where notices were removed: one neutral line with no
# instructions or promises. Kept rather than dropped, so a reply that stopped
# on "I'll search for..." does not read as if the search happened; a reply that
# was only notices becomes just this line (two user turns in a row break some
# chat templates).
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
    # The fork's stream-failure notice (removed after the 2026-10-06 merge,
    # when upstream's `[Agent stopped: …]` took over) — head plus one of its
    # two tails. Kept because chats saved before the merge still carry it.
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
    # Upstream's terminal-failure note: since the 2026-10-06 merge a
    # provider/stream failure ends the turn with "[Agent stopped: <reason>]"
    # (grep "Agent stopped:" in agent_loop.py and chat_routes.py). Same class
    # of Odysseus-written text, so it gets the same neutral marker.
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
