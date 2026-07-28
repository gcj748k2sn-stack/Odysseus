"""Guards for the two coupled document-editor defects around AI-edit diffs.

**#2467 — cross-document overwrite via a stale AI-edit diff.**
document.js keeps the AI-edit diff state (``_diffModeActive`` / ``_diffOldContent`` /
``_diffNewContent`` / ``_diffChunks``) as a module-global singleton bound to whatever
document was active when the diff opened. ``handleDocUpdate()`` and ``streamDocOpen()``
switch the active document (``activeDocId``) whenever an AI update targets a different
doc. If a pending diff is not discarded first, a later tab switch or Accept/Reject-All
flushes the stale diff's content into the now-active document and overwrites it.

**todo.md item 1 — the fix for #2467 became a data-loss bug of its own.**
``exitDiffMode(discard=True)`` restored ``_diffOldContent`` into the textarea and then
called ``saveDocument()``. But ``enterDiffMode`` deliberately leaves the textarea holding
the PRE-edit content while the docs map and the server have already advanced to the
post-edit version — so that restore-and-save is a lost update, and it passes the
compare-and-swap legitimately because ``base_version`` is the fresh one.

It fired because a single document tool call emitted ``doc_update`` twice
(``agent_loop.py``, two unguarded emitters in the same ``tool_blocks`` loop). The second
delivery re-entered ``handleDocUpdate``, hit the #2467 guard, and PUT the pre-edit buffer
back ~80ms after the edit landed as ``source="user"`` / "Manual edit". Confirmed against
document ``0680daa3`` of run ``baac5d34``: v3==v1, v6==v4, v8==v4.

The fix is three-layered, and all three layers are asserted here:
  1. ``agent_loop.py`` emits at most one ``doc_update`` per tool call.
  2. AI-driven teardowns pass ``persist: false`` — diff state is dropped without
     touching the textarea or the server. User-driven Reject-All still persists.
  3. ``saveDocument``'s 409 "newest user intent wins" retry requires a real ``input``
     event (``_userDirtyDocId``), not merely content divergence.

Kept as static source checks because document.js is browser-coupled and not importable
in pytest.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC_JS = (ROOT / "static/js/document.js").read_text()
AGENT_LOOP = (ROOT / "src/agent_loop.py").read_text()

# The AI-driven teardown: drop the diff, persist nothing.
GUARD = "exitDiffMode(true, { persist: false })"


def _function_body(src: str, signature: str) -> str:
    """Return the full text of a JS function, brace-matched from its signature.

    The parameter list is skipped by paren-matching first: destructured defaults
    like ``{ persist = true } = {}`` put braces *inside* the signature, and
    brace-matching straight from ``index("{")`` would terminate on those instead
    of on the function body.
    """
    start = src.index(signature)
    i = src.index("(", start)
    pdepth = 0
    while i < len(src):
        if src[i] == "(":
            pdepth += 1
        elif src[i] == ")":
            pdepth -= 1
            if pdepth == 0:
                break
        i += 1
    depth = 0
    i = src.index("{", i)
    while i < len(src):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start : i + 1]
        i += 1
    raise AssertionError(f"unbalanced braces after {signature!r}")


HANDLE_DOC_UPDATE = _function_body(DOC_JS, "export function handleDocUpdate(data)")
STREAM_DOC_OPEN = _function_body(DOC_JS, "export function streamDocOpen(title, language)")
EXIT_DIFF_MODE = _function_body(DOC_JS, "function exitDiffMode(discard")
SAVE_DOCUMENT = _function_body(DOC_JS, "export async function saveDocument(")


# --- #2467: the diff must still be discarded before the active doc switches ---

def test_handle_doc_update_discards_pending_diff():
    # A new AI update on a different document must not leave a stale diff bound
    # to the old doc, or a later tab switch / Accept-All overwrites the wrong doc.
    assert GUARD in HANDLE_DOC_UPDATE


def test_diff_discard_runs_before_active_doc_is_switched():
    # The discard must run while activeDocId still points at the previously
    # active doc, so the teardown is scoped to THAT doc — not the new one.
    # Any activeDocId reassignment inside handleDocUpdate must come after it.
    assert HANDLE_DOC_UPDATE.index(GUARD) < HANDLE_DOC_UPDATE.index("activeDocId = docId;")


def test_stream_doc_open_discards_pending_diff_before_switching():
    # The AI-creates-a-new-document path switches activeDocId inside
    # streamDocOpen (before any doc_update reaches handleDocUpdate), so the guard
    # must be here too — and before streamDocOpen reassigns activeDocId, or the
    # streamed new doc gets overwritten by the stale diff (the issue's own repro).
    assert GUARD in STREAM_DOC_OPEN
    assert STREAM_DOC_OPEN.index(GUARD) < STREAM_DOC_OPEN.index("activeDocId = docId;")


# --- Layer 1: one tool call, one doc_update ---

def test_agent_loop_emits_doc_update_at_most_once_per_tool_call():
    # Two emitters sit in the same `for i, block in enumerate(tool_blocks)` loop.
    # Both firing delivered the event twice, which is what sprang the trap in
    # handleDocUpdate. Whichever emitter runs second must be guarded by the flag.
    emitters = [m.start() for m in re.finditer(r'"type": "doc_update"', AGENT_LOOP)]
    assert len(emitters) >= 2, "expected the two known doc_update emitters"
    assert "doc_update_emitted = False" in AGENT_LOOP, "per-block dedup flag is missing"
    assert "doc_update_emitted = True" in AGENT_LOOP, "first emitter must set the flag"
    assert "not doc_update_emitted" in AGENT_LOOP, "second emitter must check the flag"

    # And the flag must be reset per block, not per round, or the first document
    # tool call in a turn would suppress every later one.
    reset_at = AGENT_LOOP.index("doc_update_emitted = False")
    loop_at = AGENT_LOOP.index("for i, block in enumerate(tool_blocks):")
    assert loop_at < reset_at


# --- Layer 2: an AI-driven teardown must never persist ---

def test_exit_diff_mode_supports_non_persisting_teardown():
    assert "function exitDiffMode(discard, { persist = true } = {})" in DOC_JS


def test_non_persisting_teardown_neither_restores_nor_saves():
    # persist:false must skip BOTH halves of the lost update: the textarea
    # restore (which reintroduces pre-edit content) and the PUT that ships it.
    saves = [m.start() for m in re.finditer(r"saveDocument\(", EXIT_DIFF_MODE)]
    assert len(saves) == 1, "exitDiffMode should have exactly one save path"
    gate = EXIT_DIFF_MODE.index("if (persist) {")
    assert gate < saves[0], "the save must sit inside the persist gate"
    # The unconditional restore must now sit behind a persist check.
    assert "if (!persist) {" in EXIT_DIFF_MODE
    assert EXIT_DIFF_MODE.index("if (!persist) {") < EXIT_DIFF_MODE.index(
        "textarea.value = _diffOldContent"
    )


def test_every_ai_driven_teardown_passes_persist_false():
    # These four callers are all AI-driven: the user did not ask to reject the
    # edit, so nothing may be written back. A bare exitDiffMode(true) in any of
    # them re-arms the data loss.
    for signature in (
        "export function handleDocUpdate(data)",
        "export function streamDocOpen(title, language)",
        "export function handleDocSuggestions(data)",
        "function enterDiffMode(oldContent, newContent)",
    ):
        body = _function_body(DOC_JS, signature)
        assert GUARD in body, f"{signature} must abandon the diff without persisting"
        assert "exitDiffMode(true);" not in body, f"{signature} still persists a revert"


def test_user_driven_reject_all_still_persists():
    # The counterpart: a user pressing Reject-All / Escape / switching tabs IS
    # expressing intent to undo the AI's edit, and must still be written back.
    # Regressing these to persist:false would silently discard the user's choice.
    assert DOC_JS.count("exitDiffMode(true);") >= 3


# --- Layer 3: the 409 retry needs real user input, not just divergence ---

def test_conflict_retry_requires_a_real_input_event():
    # "Newest user intent wins" deliberately overwrites a newer server version.
    # Content divergence alone reaches it from any programmatic textarea write —
    # which is how the diff-restored buffer clobbered v7. Require _userDirtyDocId.
    assert "_userDirtyDocId" in SAVE_DOCUMENT
    assert "const userTyped = contentDiverged && _userDirtyDocId === savingDocId;" in SAVE_DOCUMENT


def test_user_dirty_flag_is_only_set_from_dom_input_events():
    # The flag's whole value is that browsers do not fire `input` for
    # `textarea.value = ...`. If _markUserDirty() is ever called from anywhere
    # but an input listener, it stops distinguishing user edits from code edits.
    calls = list(re.finditer(r"_markUserDirty\(\);", DOC_JS))
    # The editor textarea, the email rich body and the email header fields all
    # feed saveCurrentToMap, so all three must mark intent or their genuine
    # edits get misread as stale writes and silently dropped on a 409.
    assert len(calls) >= 3, "expected every user-input surface to mark intent"
    for m in calls:
        preceding = DOC_JS[max(0, m.start() - 400):m.start()]
        assert "addEventListener('input'" in preceding, (
            "_markUserDirty() must only be called from an 'input' listener"
        )


# --- Every client write must say which path produced it ------------------------

def test_save_document_accepts_and_forwards_a_reason_label():
    # Every client write lands as source="user" / "Manual edit", so typing, a queued
    # autosave, a diff-review click and a diff teardown were indistinguishable in
    # document_versions. That is why diagnosing item 1 and the blend rows needed a
    # replay harness rather than one SQL query.
    assert "reason = null" in SAVE_DOCUMENT, "saveDocument must take a reason"
    assert "summary: forceVersion ? 'Saved version' : (reason || undefined)" in SAVE_DOCUMENT, (
        "the reason must reach the server as the version summary"
    )


def test_no_silent_save_is_left_unlabelled():
    # An unlabelled silent save writes an anonymous "Manual edit" row and puts us
    # straight back to guessing. Manual (non-silent) saves may stay unlabelled —
    # those genuinely are the user pressing save.
    unlabelled = re.findall(r"saveDocument\(\{ silent: true \}\)", DOC_JS)
    assert not unlabelled, f"{len(unlabelled)} silent save(s) carry no reason label"


def test_diff_paths_are_distinguishable_from_typing():
    # A diff-originated row must name itself rather than looking like typing.
    for label in ("Diff review — rejected all", "Diff review — applied"):
        assert label in DOC_JS, f"missing write label: {label}"


def test_resolving_a_chunk_does_not_write_to_the_server():
    # A review is a transaction: it commits when it ends, not on every click.
    #
    # `_resolveChunk` used to call saveDocument() after each decision, and because
    # an un-reviewed chunk rendered as its OLD side, that write rolled back every
    # change the user had not yet looked at. Doc 92f3b2a0 v3 is one Accept click
    # that resurrected twelve pre-edit sections and left the document asserting
    # both versions of each. The label it wrote — "Diff review — chunk resolved" —
    # is how it was caught, and must not come back.
    body = _function_body(DOC_JS, "function _resolveChunk(chunkId, accept)")
    assert "saveDocument(" not in body, "_resolveChunk must not persist mid-review"
    assert "_applyResolvedChunksToTextarea()" in body, "the buffer still updates"
    assert "Diff review — chunk resolved" not in DOC_JS


def test_an_unreviewed_chunk_is_never_treated_as_rejected():
    # Both the live preview and the committed result must revert a chunk ONLY on
    # an explicit rejection. Falling through to the old side for an un-reviewed
    # chunk is what manufactured the self-contradicting documents (TODO item 3).
    for signature in ("function _applyResolvedChunksToTextarea()",
                      "function exitDiffMode(discard"):
        body = _function_body(DOC_JS, signature)
        assert "chunk.resolved && !chunk.accepted" in body, (
            f"{signature} must revert only on an explicit rejection"
        )
        assert "if (chunk && chunk.accepted) {" not in body, (
            f"{signature} still uses the old accepted-or-revert rule"
        )


def test_user_dirty_flag_is_cleared_once_synced():
    # Left set, the flag would make every later stale autosave look like user
    # intent and re-open the overwrite path.
    assert "if (_userDirtyDocId === savingDocId) _userDirtyDocId = null;" in SAVE_DOCUMENT
    assert SAVE_DOCUMENT.count("_userDirtyDocId = null;") >= 2
