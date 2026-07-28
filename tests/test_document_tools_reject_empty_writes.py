"""An empty document write must be refused, never applied.

Run 8c80cf8d (2026-07-19) — the first session to run the item 8 "cross-round
stall" nudge. Told to *"finish the job NOW using the appropriate tool"*, a model
that had gathered information but written nothing called `update_document` with
no content. A 6186-character document became **zero bytes**, recoverable only
from `document_versions`. It then created two empty "Untitled" documents and
emptied one of those twice: five zero-length versions in four minutes, against
none in the preceding 79.

The nudge was reverted, but it only exposed the real defect. `edit_document` has
refused empty content since 2026-07-18; `update_document` and `create_document`
never did, so any empty call from any cause would destroy a document. That is a
data-loss bug independent of what prompted the call, and this pins it.

`update_document` takes the FULL new document text, so "no content" and "delete
everything" are indistinguishable at the call site — which is exactly why the
empty case must be refused rather than honoured. Deliberate emptying is
available through `edit_document`, where the FIND text makes the intent explicit.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SRC = (ROOT / "src/agent_tools/document_tools.py").read_text()


def _tool_body(class_name: str) -> str:
    start = SRC.index(f"class {class_name}")
    nxt = SRC.find("\nclass ", start + 1)
    return SRC[start:nxt if nxt != -1 else len(SRC)]


@pytest.mark.parametrize("tool", ["UpdateDocumentTool", "CreateDocumentTool"])
def test_empty_content_is_refused(tool):
    body = _tool_body(tool)
    assert 'if not (content or "").strip():' in body, (
        f"{tool} must refuse an empty write"
    )
    assert "received no content" in body, f"{tool} must say why it refused"


def test_update_refuses_before_touching_the_document():
    """The guard must precede every path that could write.

    In particular it must run BEFORE the email coercion, which rebuilds content
    from the existing document and would turn an empty body into a valid-looking
    header block — laundering the empty write into something that looks real.
    """
    body = _tool_body("UpdateDocumentTool")
    guard_at = body.index('if not (content or "").strip():')
    coerce_at = body.index("_coerce_email_document_content")
    assert guard_at < coerce_at, "empty check must precede the email coercion"

    for writer in ("doc.current_content =", "DocumentVersion(", "db.commit()"):
        if writer in body:
            assert guard_at < body.index(writer), f"empty check must precede {writer}"


def test_refusal_is_an_error_not_a_silent_noop():
    """A silent no-op would read as success and the model would move on.

    It has to come back as an error so the retry directive fires and the user's
    correction actually gets made.
    """
    body = _tool_body("UpdateDocumentTool")
    guard_at = body.index('if not (content or "").strip():')
    tail = body[guard_at:guard_at + 1200]
    assert '"error"' in tail
    assert "edit_document" in tail, "tell the model the narrower alternative"


def test_the_loss_is_logged_with_its_size():
    """The one thing worth knowing after the fact is how much was nearly lost."""
    body = _tool_body("UpdateDocumentTool")
    assert "logger.warning" in body
    assert "len(doc.current_content or \"\")" in body


def test_edit_document_still_refuses_empty_content():
    """The precedent this fix follows — must not regress."""
    body = _tool_body("EditDocumentTool")
    assert 'if not (content or "").strip():' in body
    assert "received no content" in body


def test_the_reverted_nudge_is_not_reinstated():
    """The directive that triggered this must not come back without a guard.

    Removing it is not the whole fix, but reintroducing an imperative "act now"
    instruction aimed at a model with nothing to write is how this happened.
    """
    loop = (ROOT / "src/agent_loop.py").read_text()
    assert "_stall_nudge_count += 1" not in loop, (
        "the cross-round stall nudge is reverted; see the comment at its site"
    )
    assert "REVERTED 2026-07-19" in loop, "the reason must stay next to the code"
