"""The known-facts check must reach the user and must not drive the model.

Deliberately the same two properties, and the same shape, as
`test_document_fidelity_wiring.py` — item 2a and item 2b are two halves of one
split and a divergence between their safety guarantees would be a bug in
itself.

1. Findings surface in the closing summary beside `stale_values` and `fidelity`.
   A lint whose findings only reach the logs is the failure in notes/todo.md,
   "Partial edits leave documents contradicting themselves" (item 3 at the time
   of writing — cited by title because a bare number across files has no
   integrity check): `find_stale_values()` was correct and model-agnostic for
   weeks while its warning rendered through a gated summary nobody saw on this
   model.

2. It is REPORT-ONLY, and this file is where that is enforced. There is a
   specific temptation here that item 2a does not have: the findings are
   *corrections*, and feeding them back to the model looks like an obvious
   improvement. Item 8's retry nudge is the precedent — told to "finish the job
   NOW", the model called `update_document` with empty content and wiped a
   6186-character document, five zero-length versions in four minutes. Anything
   that acts on these findings needs its own guard proving the retry can only
   write content it actually holds, and tests that bound what it can do rather
   than assert that it exists.
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
        "tool": "create_document", "title": "Pink Oyster Growth Phases", "version": 1,
        "known_facts": ["“Cool down by 3-5°F” — P. djamor is thermophilic and needs no cold shock."],
    })
    assert "Contradicts what we already established" in line
    assert "cold shock" in line


def test_summary_without_findings_is_unchanged():
    info = {"tool": "create_document", "title": "Notes", "version": 1}
    assert "Contradicts what we already established" not in _doc_tool_summary(info)


def test_findings_are_capped_in_the_summary():
    line = _doc_tool_summary({
        "tool": "create_document", "title": "T", "version": 1,
        "known_facts": [f"finding {i}" for i in range(9)],
    })
    assert "(+5 more)" in line
    assert "finding 8" not in line


def test_all_three_lints_coexist():
    """stale_values, fidelity and known_facts answer different questions and a
    document can fail all three at once."""
    line = _doc_tool_summary({
        "tool": "edit_document", "title": "T", "version": 3,
        "stale_values": ["20-30°C"],
        "fidelity": ["`duty` is a raw register"],
        "known_facts": ["“cooler than other Pleurotus” — backwards"],
    })
    assert "still appear" in line
    assert "Doesn't match the source" in line
    assert "Contradicts what we already established" in line


def test_the_call_is_wrapped_so_a_lint_cannot_break_a_turn():
    tree = ast.parse(SRC)
    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "check_known_facts"
    ]
    assert len(calls) == 1, f"expected exactly one call site, found {len(calls)}"
    protected = any(
        any(isinstance(c, ast.Call) and getattr(c.func, "id", None) == "check_known_facts"
            for c in ast.walk(handler_parent))
        for handler_parent in [n for n in ast.walk(tree) if isinstance(n, ast.Try)]
    )
    assert protected, "check_known_facts is not inside a try block"


@pytest.mark.parametrize("forbidden", [
    "_doc_edit_retry_directive",
    "_relevant_tools",
    "tool_choice",
])
def test_findings_never_reach_a_model_facing_path(forbidden):
    for line in SRC.split("\n"):
        if "known_facts" in line and forbidden in line:
            pytest.fail(f"known-facts findings reached a model-facing path: {line.strip()}")


def test_known_facts_is_only_ever_read_for_reporting():
    reads = [l.strip() for l in SRC.split("\n")
             if '"known_facts"' in l or 'get("known_facts")' in l]
    assert reads, "nothing reads known_facts — the wiring is dead"
