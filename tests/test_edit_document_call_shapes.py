"""Argument shapes for edit_document/suggest_document structured calls.

Observed 2026-07-18 (run b5fe4ef5, turn 2, "fact check and correct the
dokument"). The turn ran web_search -> edit_document -> update_plan -> stop in
526 seconds and never touched the document. The stored tool event was:

    {"round": 2, "tool": "edit_document", "command": "",
     "output": "No valid <<<FIND>>>...<<<REPLACE>>>...<<<END>>> blocks found"}

The model was blamed for malformed FIND blocks, then for emitting a bare fence
header. Neither was true: an empty fence never reaches dispatch (only
BUILTIN_EMAIL_TOOLS survive that check in parse_tool_blocks), so the call
arrived through the structured/markup path, where the converter accepted
exactly one argument shape -- a well-formed `edits` list -- and coerced
everything else to [], yielding an empty content string it then dispatched.

These tests pin the shapes local models actually emit, and pin the failure
message for the genuinely-empty case so a future call can't be misread as a
syntax error again.
"""

import json

from src.agent_tools.document_tools import parse_edit_blocks
from src.tool_schemas import function_call_to_tool_block


def _content(args) -> str:
    block = function_call_to_tool_block("edit_document", json.dumps(args))
    assert block is not None, f"call was dropped entirely: {args!r}"
    return block.content


def _one_edit(args, find, replace):
    edits = parse_edit_blocks(_content(args))
    assert edits == [{"find": find, "replace": replace}], f"got {edits!r} from {args!r}"


def test_canonical_edits_list_still_works():
    """The shape that already worked must keep working."""
    _one_edit(
        {"edits": [{"find": "20-30°C", "replace": "24-30°C"}]},
        "20-30°C",
        "24-30°C",
    )


def test_multiple_edits_preserved_in_order():
    content = _content({"edits": [
        {"find": "a", "replace": "b"},
        {"find": "c", "replace": "d"},
    ]})
    assert parse_edit_blocks(content) == [
        {"find": "a", "replace": "b"},
        {"find": "c", "replace": "d"},
    ]


def test_single_dict_instead_of_list():
    """`edits` as a bare object rather than a one-element array."""
    _one_edit({"edits": {"find": "<800 ppm", "replace": "<1000 ppm"}}, "<800 ppm", "<1000 ppm")


def test_double_encoded_json_edits():
    """`edits` arrives as a JSON *string* -- very common from local models."""
    _one_edit(
        {"edits": json.dumps([{"find": "16-24°C", "replace": "20-30°C"}])},
        "16-24°C",
        "20-30°C",
    )


def test_pair_hoisted_to_top_level():
    """find/replace given as top-level arguments, no `edits` wrapper."""
    _one_edit({"find": "3-4 weeks", "replace": "7-28 days"}, "3-4 weeks", "7-28 days")


def test_old_new_string_aliases():
    """edit_file's argument names leaking into edit_document."""
    _one_edit(
        {"edits": [{"old_string": "0.4%", "new_string": "500-800 ppm"}]},
        "0.4%",
        "500-800 ppm",
    )


def test_raw_markup_in_edits_arg():
    """The model pre-formatted the blocks and passed them as the argument."""
    _one_edit(
        {"edits": "<<<FIND>>>\nold text\n<<<REPLACE>>>\nnew text\n<<<END>>>"},
        "old text",
        "new text",
    )


def test_raw_markup_under_content_key():
    _one_edit(
        {"content": "<<<FIND>>>\nold text\n<<<REPLACE>>>\nnew text\n<<<END>>>"},
        "old text",
        "new text",
    )


def test_list_of_markup_strings():
    content = _content({"edits": [
        "<<<FIND>>>\na\n<<<REPLACE>>>\nb\n<<<END>>>",
        "<<<FIND>>>\nc\n<<<REPLACE>>>\nd\n<<<END>>>",
    ]})
    assert parse_edit_blocks(content) == [
        {"find": "a", "replace": "b"},
        {"find": "c", "replace": "d"},
    ]


def test_empty_call_still_dispatches_rather_than_vanishing():
    """A call with nothing usable must NOT be dropped.

    Returning None here drops the block, and a dropped block produces a round
    with no tool event and no text -- which is how b5fe4ef5 ended up saving a
    bare "Done." with the document untouched. Dispatching an empty call is
    worse output but visible failure, and visible is what the retry needs.
    """
    block = function_call_to_tool_block("edit_document", json.dumps({}))
    assert block is not None
    assert block.content == ""


def test_suggest_document_shapes():
    block = function_call_to_tool_block(
        "suggest_document",
        json.dumps({"suggestions": {"find": "a", "replace": "b", "reason": "clearer"}}),
    )
    assert block is not None
    assert "<<<FIND>>>\na\n<<<SUGGEST>>>\nb\n<<<REASON>>>\nclearer\n<<<END>>>" in block.content


def test_empty_and_unparseable_errors_are_distinct():
    """The two failures must not share a message.

    They have different causes and different fixes: empty means the call
    carried nothing, unparseable means the markers are wrong. Collapsing them
    is what let a converter bug read as a model syntax error for a whole
    debugging round. Both branches return before any database access, so this
    exercises the real tool.
    """
    import asyncio

    from src.agent_tools.document_tools import EditDocumentTool

    tool = EditDocumentTool()
    empty = asyncio.run(tool.execute("", {}))
    broken = asyncio.run(tool.execute("<<<FIND>>>\nsome text\n(no other markers)", {}))

    assert "received no content" in empty["error"]
    assert "received no content" not in broken["error"]
    assert "three markers" in broken["error"]
    assert empty["exit_code"] == 1 and broken["exit_code"] == 1
