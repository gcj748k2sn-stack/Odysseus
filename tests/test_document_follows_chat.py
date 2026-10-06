"""Leaving a chat leaves its document (notes/todo.md item 62).

Seen 2026-10-05 23:31 and 23:38: the "Pink Oyster" document open in the editor
moved from chat to chat. "New Chat" (`createDirectChat`) and switching to a
chat with no documents only called `closePanel()`, which hides the panel but
keeps `activeDocId`; `chat.js` sends `getCurrentDocId()` as `active_doc_id`, and
the server rebinds a cross-session document to the sending chat.

There is no JS harness, so these are source checks on the three properties the
fix depends on — the wiring at both call sites, the save-then-empty order in
`releaseCurrentDoc`, and the `saveDocument` invariant that makes that order
safe. Live check: in the item.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC_JS = (ROOT / "static" / "js" / "document.js").read_text(encoding="utf-8")
SESSIONS_JS = (ROOT / "static" / "js" / "sessions.js").read_text(encoding="utf-8")


def _body(src, header_re):
    """Text of the function whose header matches, by brace counting."""
    m = re.search(header_re, src)
    assert m, f"function not found: {header_re}"
    i = src.index("{", m.end() - 1)
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
    raise AssertionError("unbalanced braces")


RELEASE = _body(DOC_JS, r"export function releaseCurrentDoc\([^)]*\)\s*\{")


def test_release_is_exported_on_the_module_object():
    obj = DOC_JS[DOC_JS.index("const documentModule = {"):]
    obj = obj[:obj.index("};")]
    assert re.search(r"^\s*releaseCurrentDoc,\s*$", obj, re.M)


def test_release_saves_before_it_empties_the_editor():
    order = [RELEASE.index(s) for s in ("saveCurrentToMap()", "saveDocument(", "showEmptyState()")]
    assert order == sorted(order), "buffer → map → save → empty, in that order"
    assert "delete textarea.dataset.docId" in RELEASE
    assert RELEASE.index("if (!activeDocId) return;") < order[0]


def test_save_document_captures_content_before_its_first_await():
    """releaseCurrentDoc empties the editor right after calling saveDocument
    without awaiting it. That only loses nothing because saveDocument reads
    the id and the content synchronously — if a refactor moves either behind
    an await, release would save an empty document."""
    body = _body(DOC_JS, r"export async function saveDocument\([^)]*\)\s*\{")
    first_await = body.index("await ")
    assert body.index("const savingDocId = activeDocId") < first_await
    assert body.index("const contentToSave =") < first_await


def test_new_chat_releases_the_document():
    body = _body(SESSIONS_JS, r"export function createDirectChat\([^)]*\)\s*\{")
    assert "releaseCurrentDoc('new-chat')" in body
    # after the panel is closed, so closePanel() still saves into the map first
    assert body.index("closePanel()") < body.index("releaseCurrentDoc('new-chat')")


def test_switching_to_a_chat_without_documents_releases_the_document():
    i = SESSIONS_JS.index("if (hasDocs) {")
    branch = SESSIONS_JS[i:i + 1200]
    else_part = branch[branch.index("} else {"):]
    assert "releaseCurrentDoc('switch-to-chat-without-documents')" in else_part
    assert else_part.index("releaseCurrentDoc(") < else_part.index("closePanel()")


def test_chat_with_documents_still_goes_through_load_session_docs():
    """Negative control: the path that already cleared the document is unchanged."""
    i = SESSIONS_JS.index("if (hasDocs) {")
    has_docs = SESSIONS_JS[i:SESSIONS_JS.index("} else {", i)]
    assert "loadSessionDocs(id, { restoreMode: true })" in has_docs
    assert "releaseCurrentDoc" not in has_docs


def test_fresh_chat_path_releases_the_document():
    """Mobile New Chat and _handleNewChatAction's no-models fallback go through
    app.js _startFreshChat(), not sessions.createDirectChat()."""
    app_js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    body = _body(app_js, r"function _startFreshChat\(\)\s*\{")
    assert "releaseCurrentDoc('fresh-chat')" in body
    assert body.index("closePanel()") < body.index("releaseCurrentDoc('fresh-chat')")
