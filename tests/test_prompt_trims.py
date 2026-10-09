"""Prompt text that does not apply to the turn's tools is left out.

A plain question on a local model was given the "Odysseus Terminus
local-machine mode" rules (~1,400 chars: "the user referred to this computer
… not ordinary chat"), because ask_user/update_plan, sent every turn, are in
the Terminus toolset. The date/time context named manage_calendar and
manage_tasks even when both were switched off.
"""
import pytest

import src.agent_loop as al
from src import prompt_trims as P
from src.tool_index import ALWAYS_AVAILABLE

MACHINE_HEADER = "Odysseus Terminus local-machine mode"
CAL_LINE = "When scheduling calendar events with manage_calendar"
TASK_LINE = "When scheduling a task with manage_tasks"


def _prompt(tools, workspace=None):
    out, _ = al._build_system_prompt(
        [{"role": "user", "content": "Give me three ideas for my garden project"}],
        "bonsai2-27b", None, None, set(), relevant_tools=set(tools), compact=True, workspace=workspace)
    system = "\n".join(m["content"] for m in out if m["role"] == "system")
    user_ctx = "\n".join(m["content"] for m in out if m["role"] == "user" and isinstance(m["content"], str))
    return system, user_ctx


def test_a_plain_turn_gets_no_local_machine_rules():
    system, _ = _prompt(ALWAYS_AVAILABLE)
    assert "## Base rules" in system
    assert MACHINE_HEADER not in system


def test_a_turn_with_file_or_shell_tools_still_gets_them():
    system, _ = _prompt(al._terminus_toolset({"files"}))
    assert MACHINE_HEADER in system


def test_a_workspace_turn_keeps_the_workspace_rules_instead():
    system, _ = _prompt(al._terminus_toolset({"files"}), workspace="/tmp/ws")
    assert "Workspace coding mode" in system and MACHINE_HEADER not in system


def test_calendar_and_task_lines_only_with_their_tools():
    _, ctx = _prompt(ALWAYS_AVAILABLE)
    assert "## Current date and time" in ctx
    assert CAL_LINE not in ctx and TASK_LINE not in ctx
    _, ctx = _prompt(set(ALWAYS_AVAILABLE) | {"manage_calendar"})
    assert CAL_LINE in ctx and TASK_LINE not in ctx


def test_no_tool_selection_changes_nothing():
    msg = {"role": "user", "content": f"x\n{CAL_LINE}, y\n{TASK_LINE}, z\n"}
    assert P.trim_datetime_message(msg, None) is msg
    assert not P.wants_local_computer_rules(None)


@pytest.mark.parametrize("tools", [{"ask_user", "update_plan"}, {"web_search", "todowrite", "get_workspace"}])
def test_helpers_alone_are_not_machine_work(tools):
    assert not P.wants_local_computer_rules(tools)
