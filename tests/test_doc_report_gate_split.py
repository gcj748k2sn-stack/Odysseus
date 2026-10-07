"""The document *reporting* path must not be gated on the finetune model.

notes/todo.md, *"Closing summary under-reports, and sometimes says nothing"*
(item 7 as of 2026-07-28; this docstring cited **#2** until then, which is the
unrelated fact-check-inversion item — cite by title, numbers rot).
Closed diagnosis: notes/resolvedissues.md, *"The document reporting path was dead
code on the current model — split gate"*.

`_doc_tool_summary()` sat behind
`_ody_doc_tool_completed` -> `_ody_doc_finetune_mode` -> `_ody_qwen_finetune_model`,
which is `model.lower().startswith("odysseus-qwen3")`. `qwen3.5:9b-32k` does not
match, so the closing summary and the stale-value warning were dead code on the
model actually in use. Observed live on run c436d4a8 (2026-07-18): a turn ran
`update_document`, wrote v2, and reported "Done." — the user was told nothing
about what changed, on a turn whose entire point was the corrections.

The fix is a SPLIT, not a widening. Widening `_ody_doc_finetune_mode` would also
switch on tool narrowing (`_relevant_tools` cut to five document tools) and the
loop break, which would kill the unprompted create_document -> edit_document
self-correction this model does. Reporting is safe for every model; breaking the
loop is not.

These tests pin both halves: the behaviour of the synthesized closing line, and
the structural invariant that the two are no longer one condition.
"""

import ast
import json
import textwrap
from pathlib import Path

from src.agent_loop import DOC_TOOLS
from src.turn_report import _closing_doc_summary

AGENT_LOOP = Path(__file__).resolve().parent.parent / "src" / "agent_loop.py"


def _delta(chunk):
    assert chunk.startswith("data: ")
    return json.loads(chunk[len("data: "):])["delta"]


# --------------------------------------------------------------------------
# Behaviour: the synthesized closing line
# --------------------------------------------------------------------------

def test_silent_document_turn_reports_what_changed():
    """The c436d4a8 shape: document updated, model wrote nothing."""
    response, chunk = _closing_doc_summary("", {
        "tool": "update_document",
        "title": "Pink Oyster Mushroom Growth Phases",
        "version": 2,
        "applied": 1,
        "skipped": 0,
    })
    assert "Pink Oyster Mushroom Growth Phases" in response
    assert "v2" in response
    assert response != "Done."
    assert _delta(chunk) == response


def test_stale_value_warning_now_reaches_the_user():
    """Previously logs-only on this model: find_stale_values() is model-agnostic,
    but its warning rendered through the gated summary."""
    response, chunk = _closing_doc_summary("", {
        "tool": "edit_document", "title": "Guide", "version": 4,
        "applied": 9, "skipped": 0, "stale_values": ["0.4%"],
    })
    assert "Still inconsistent" in response
    assert "`0.4%`" in response
    assert chunk is not None


def test_models_own_summary_is_left_alone():
    """A real summary beats a synthesized one."""
    written = "I corrected the fruiting temperature and the CO2 threshold."
    response, chunk = _closing_doc_summary(written, {
        "tool": "edit_document", "title": "Guide", "version": 2, "applied": 2,
    })
    assert response == written
    assert chunk is None


def test_whitespace_only_response_counts_as_empty():
    response, chunk = _closing_doc_summary("   \n  ", {
        "tool": "create_document", "title": "Guide", "version": 1,
    })
    assert "Created" in response
    assert chunk is not None


def test_no_document_tool_means_no_synthesized_line():
    """Must not invent a document summary for a turn that touched no document."""
    assert _closing_doc_summary("", {}) == ("", None)


def test_unreportable_info_does_not_produce_an_empty_delta():
    """_doc_tool_summary returns "" for junk; don't stream an empty bubble."""
    response, chunk = _closing_doc_summary("", {"tool": "unknown_tool"})
    assert chunk is None or _delta(chunk).strip()


def test_all_four_document_tools_are_reportable():
    assert set(DOC_TOOLS) == {
        "create_document", "update_document", "edit_document", "suggest_document"
    }
    for tool in DOC_TOOLS:
        response, _ = _closing_doc_summary("", {
            "tool": tool, "title": "Guide", "version": 2, "applied": 1,
        })
        assert response.strip(), f"{tool} produced no closing line"


# --------------------------------------------------------------------------
# Structure: the gate is split, and must stay split
# --------------------------------------------------------------------------

def _guard_names(node, tree):
    """Names tested by every `if` enclosing `node` inside the module."""
    names = set()
    for parent in ast.walk(tree):
        if not isinstance(parent, ast.If):
            continue
        body = list(ast.walk(parent))
        if node in body and node not in list(ast.walk(parent.test)):
            names |= {n.id for n in ast.walk(parent.test) if isinstance(n, ast.Name)}
    return names


def _assignments_to(tree, target_name):
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == target_name:
                    out.append(node)
    return out


def test_report_data_is_built_for_every_model():
    """`_ody_doc_tool_info` must not sit behind the finetune flag.

    This is the whole bug: merging these two conditions is what made the
    summary dead code. If someone re-merges them, this fails.
    """
    tree = ast.parse(AGENT_LOOP.read_text())
    populating = [
        a for a in _assignments_to(tree, "_ody_doc_tool_info")
        if (isinstance(a.value, ast.Dict) and a.value.keys)
        or (isinstance(a.value, ast.Call)
            and getattr(a.value.func, "id", None) == "record_doc_tool_result")
    ]
    assert populating, "no populating assignment to _ody_doc_tool_info found"
    for assign in populating:
        guards = _guard_names(assign, tree)
        assert "_ody_doc_finetune_mode" not in guards, (
            "the document report payload is gated on _ody_doc_finetune_mode again — "
            "that makes the closing summary and stale-value warning dead code on "
            "every model except the Odysseus finetune. See notes/todo.md, \"Closing summary under-reports\"."
        )


def test_loop_break_stays_gated_on_the_finetune_model():
    """The other half. Ungating this would narrow tools to five and break the
    loop on first success, killing the create -> edit self-correction."""
    tree = ast.parse(AGENT_LOOP.read_text())
    completions = [
        a for a in _assignments_to(tree, "_ody_doc_tool_completed")
        if isinstance(a.value, ast.Constant) and a.value.value is True
    ]
    assert completions, "no `_ody_doc_tool_completed = True` found"
    for assign in completions:
        assert "_ody_doc_finetune_mode" in _guard_names(assign, tree), (
            "the loop break is no longer gated on _ody_doc_finetune_mode — "
            "this stops the agent at the first successful document tool for "
            "every model. See notes/todo.md, \"Closing summary under-reports\"."
        )


def test_tool_narrowing_and_tool_choice_remain_gated():
    """Widening the gate was the tempting fix; these are what it would have
    switched on. Pinned so the split can't quietly become a widening."""
    src = AGENT_LOOP.read_text()
    assert "if _ody_doc_finetune_mode and _relevant_tools is not None:" in src
    assert "tool_choice_none=_ody_doc_finetune_mode" in src
