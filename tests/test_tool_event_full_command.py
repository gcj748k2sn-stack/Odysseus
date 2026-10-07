"""Document tool arguments must survive into the persisted tool event.

`tool_event["command"]` is `block.content.split("\\n")[0][:80]`, which for an
edit is literally `<<<FIND>>>` — enough to know a call happened and nothing
about what it asked for. That blocked diagnosis three times; see notes/todo.md,
"Failures aren't replayable".

These pin the two properties a replay harness depends on:

  1. the full arguments are persisted for document tools, on success as well as
     failure — c7da3649 succeeded with "v5, 2 edit(s)" while silently skipping a
     third FIND block, and a failure-only rule would have discarded it;
  2. a clipped record is *marked* clipped, so a replay cannot quietly reproduce
     a different call than the one that ran.

Source-level, deliberately: driving a full agent turn to assert a persistence
detail would couple these to the whole loop. The behaviour under test is the
`_cap_persisted_command` contract plus the fact that the writer is reached from
the document-tool branch, which the AST check pins.
"""
import ast
import pathlib

import pytest

from src.agent_loop import _cap_persisted_command
from src.turn_report import _PERSISTED_COMMAND_MAX

AGENT_LOOP = pathlib.Path(__file__).resolve().parents[1] / "src" / "agent_loop.py"


def test_short_command_is_stored_verbatim():
    cmd = '<<<FIND>>>\nfruiting 14-21°C\n<<<REPLACE>>>\nfruiting 20-30°C\n<<<END>>>'
    assert _cap_persisted_command(cmd) == cmd


def test_command_at_the_limit_is_not_truncated():
    cmd = "x" * _PERSISTED_COMMAND_MAX
    out = _cap_persisted_command(cmd)
    assert out == cmd
    assert "truncated" not in out


def test_oversized_command_is_clipped_and_says_so():
    cmd = "y" * (_PERSISTED_COMMAND_MAX + 500)
    out = _cap_persisted_command(cmd)
    assert out.startswith("y" * _PERSISTED_COMMAND_MAX)
    # The marker must state how much went missing: a replay that cannot tell a
    # clipped record from a complete one will reproduce the wrong call.
    assert "truncated" in out
    assert "500" in out


def test_none_becomes_empty_rather_than_crashing():
    assert _cap_persisted_command(None) == ""


def test_truncation_keeps_the_head_not_the_tail():
    """FIND blocks lead the payload, so the head is the part worth keeping."""
    cmd = "<<<FIND>>>\n" + ("z" * (_PERSISTED_COMMAND_MAX * 2))
    out = _cap_persisted_command(cmd)
    assert out.startswith("<<<FIND>>>")


def _assignments_to(tree, name):
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == name:
                    out.append(node)
    return out


def test_full_command_is_persisted_through_the_cap():
    """`tool_event["full_command"]` must go through `_cap_persisted_command`.

    Assigning `full_command` raw would put an unbounded document body into
    message metadata on every edit.
    """
    tree = ast.parse(AGENT_LOOP.read_text())
    writes = [
        a for a in _assignments_to(tree, "tool_event")
        if isinstance(a.targets[0].slice, ast.Constant)
        and a.targets[0].slice.value == "full_command"
    ]
    assert writes, "nothing assigns tool_event['full_command']"
    for node in writes:
        assert isinstance(node.value, ast.Call), "full_command stored without a cap"
        assert getattr(node.value.func, "id", None) == "_cap_persisted_command", (
            "tool_event['full_command'] must be wrapped in _cap_persisted_command — "
            "an uncapped document body lands in message metadata otherwise"
        )


def test_persisted_cap_stays_sane():
    """A cap of 0 or an unbounded one both defeat the point."""
    assert 1024 <= _PERSISTED_COMMAND_MAX <= 262144
