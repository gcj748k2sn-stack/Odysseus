"""An AI document update that arrives with the panel closed must fill the editor.

notes/todo.md, *"Approving a document action with the document panel closed
always fails"* (follow-up seen live 2026-10-07 22:10). ``handleDocUpdate`` took
its ``#doc-editor-textarea`` reference before ``openPanel()`` built the editor,
so with the panel closed the reference was null: the new editor opened empty and
unstamped. ``saveDocument`` lets an unstamped buffer through, so one keystroke
(2 s autosave) or the pre-send save would have written the empty buffer over the
version the AI had just saved.

Static source checks, like ``test_document_diff_discard_on_update_js.py``:
document.js is browser-coupled and there is no JS harness. Manual check: panel
closed, an approved AI edit lands -> the editor opens showing the new text.
"""

import re
from pathlib import Path

DOC_JS = (Path(__file__).resolve().parents[1] / "static/js/document.js").read_text()


def _handle_doc_update_body():
    start = DOC_JS.index("export function handleDocUpdate(")
    end = DOC_JS.index("\n  /** Toggle version history panel */", start)
    return DOC_JS[start:end]


def test_editor_is_looked_up_again_after_open_panel():
    body = _handle_doc_update_body()
    open_at = body.index("if (!isOpen) openPanel();")
    requery = re.search(
        r"if \(!textarea\) textarea = document\.getElementById\('doc-editor-textarea'\);",
        body,
    )
    assert requery, "handleDocUpdate must re-query the editor openPanel() may have built"
    assert requery.start() > open_at
    assert "let textarea = document.getElementById('doc-editor-textarea');" in body


def test_direct_content_write_stamps_the_buffer():
    body = _handle_doc_update_body()
    assert re.search(
        r"textarea\.value = newContent;\s*textarea\.dataset\.docId = docId;", body,
    ), "a buffer written from a doc_update must carry its document's stamp"
