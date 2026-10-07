"""The fidelity check must reach the user and must not drive the model.

Two properties, both structural, both learned the hard way:

1. Findings surface in the closing summary next to `stale_values`. A lint whose
   findings only reach the logs is the failure recorded in notes/todo.md item 3
   — `find_stale_values()` was correct and model-agnostic for weeks while its
   warning rendered through a gated summary nobody saw on this model.

2. It is REPORT-ONLY. Item 8's retry nudge told an idle model to "finish the job
   NOW" and it called `update_document` with empty content, wiping a
   6186-character document — five zero-length versions in four minutes. The
   note there is explicit: a guard that makes the model *act* must have tests
   that bound what it can do, not merely assert it exists. So this file pins
   that the check appears in no prompt-building or tool-directive path.
"""
import ast
import pathlib

import pytest

from src.turn_report import _doc_tool_summary

AGENT_LOOP = pathlib.Path(__file__).parents[1] / "src" / "agent_loop.py"
# The call site moved to src/turn_report.py (record_doc_tool_result); the
# properties below hold across the whole agent-loop path, so scan both.
TURN_REPORT = AGENT_LOOP.with_name("turn_report.py")
SRC = AGENT_LOOP.read_text() + "\n" + TURN_REPORT.read_text()


def test_findings_appear_in_the_closing_summary():
    line = _doc_tool_summary({
        "tool": "create_document", "title": "Sensor Data", "version": 1,
        "fidelity": ["`duty` is a raw register, not a metric — the document prints 252."],
    })
    assert "Doesn't match the source" in line
    assert "duty" in line and "252" in line


def test_summary_without_findings_is_unchanged():
    line = _doc_tool_summary({"tool": "create_document", "title": "Notes", "version": 1})
    assert line == "Created **Notes** (v1)."
    assert "match the source" not in line


def test_findings_are_capped_in_the_summary():
    line = _doc_tool_summary({
        "tool": "create_document", "title": "T", "version": 1,
        "fidelity": [f"finding {i}" for i in range(9)],
    })
    assert "+5 more" in line
    assert line.count("- finding") == 4


def test_stale_values_and_fidelity_coexist():
    line = _doc_tool_summary({
        "tool": "edit_document", "title": "T", "version": 2, "applied": 3,
        "stale_values": ["0.4%"], "fidelity": ["`duty` is a raw register."],
    })
    assert "Still inconsistent" in line and "Doesn't match the source" in line


def _calls_named(tree, name):
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) == name]


def test_check_document_is_called_exactly_once():
    """One call site. A second would mean the check drifted into another path."""
    assert len(_calls_named(ast.parse(SRC), "check_document")) == 1


def test_the_call_is_wrapped_so_a_lint_cannot_break_a_turn():
    tree = ast.parse(SRC)
    call = _calls_named(tree, "check_document")[0]
    guarded = any(
        isinstance(node, ast.Try) and any(c is call for c in ast.walk(node))
        for node in ast.walk(tree)
    )
    assert guarded, "check_document must be inside try/except — a failing lint must not kill the turn"


@pytest.mark.parametrize("forbidden", [
    "_doc_edit_retry_directive",
    "_relevant_tools",
    "tool_choice",
])
def test_findings_never_reach_a_model_facing_path(forbidden):
    """`fidelity` must not be read anywhere that steers the model.

    Report-only is the whole safety argument. If a later change wants to act on
    these findings, it needs its own guard proving the retry can only write
    content it actually holds — see item 8 before touching this.
    """
    for line in SRC.split("\n"):
        if "fidelity" in line and forbidden in line:
            pytest.fail(f"fidelity findings reached a model-facing path: {line.strip()}")


def test_fidelity_is_only_ever_read_for_reporting():
    reads = [l.strip() for l in SRC.split("\n")
             if '"fidelity"' in l or "get(\"fidelity\")" in l]
    assert reads, "nothing reads fidelity — the wiring is dead"
    for line in reads:
        assert any(tok in line for tok in ("_ody_doc_tool_info", "info.get", 'info["fidelity"] = ')), line
