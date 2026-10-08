"""An approved document action's tool_output must not empty the editor.

notes/todo.md, *"An approved document edit empties the editor"* (seen live
2026-10-08 08:45). The approved-action replay in ``stream_agent_loop`` emits a
``tool_output`` with the raw result keys (``content``, ``version``, ``title``),
while the fallback in ``chat.js`` read only ``document_*`` keys and defaulted to
``''`` / ``1``. Right after the correct ``doc_update`` (v2), that fallback called
``handleDocUpdate`` again with empty content: the editor showed nothing, stamped
with the document's id, so any save would have written an empty version.

Static source checks: chat.js is browser-coupled and there is no JS harness.
Manual check: approve a document edit -> the editor shows the new text.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAT_JS = (ROOT / "static/js/chat.js").read_text()
AGENT_LOOP = (ROOT / "src/agent_loop.py").read_text()


def _fallback_block():
    start = CHAT_JS.index("// Native document tool calls can arrive as a completed")
    end = CHAT_JS.index("_scheduleThinkingSpinner();", start)
    return CHAT_JS[start:end]


def test_fallback_never_defaults_content_to_empty():
    block = _fallback_block()
    assert "handleDocUpdate(" in block
    assert not re.search(r"content:\s*json\.document_content\s*\|\|\s*''", block)
    assert not re.search(r"content:\s*[^,\n]*\|\|\s*''", block), (
        "an absent content field must skip the update, not apply ''"
    )


def test_fallback_requires_string_content_and_reads_raw_keys():
    block = _fallback_block()
    m = re.search(r"const (\w+) = json\.document_content \?\? json\.content;", block)
    assert m, "the fallback must accept the approved replay's raw `content` key"
    var = m.group(1)
    assert re.search(rf"&& typeof {var} === 'string'\s*\)", block)
    assert re.search(rf"content: {var},", block)
    assert "json.document_version || json.version || 1" in block


def test_approved_replay_still_sends_the_raw_keys_the_fallback_reads():
    # Couples the two halves: if the replay switches to document_* keys, the
    # ?? fallback still works; if it drops `content`, the update is skipped.
    start = AGENT_LOOP.index("approved_event = {")
    keys = AGENT_LOOP[start:start + 1200]
    for key in ('"doc_id"', '"content"', '"version"'):
        assert key in keys
