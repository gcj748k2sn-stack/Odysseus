"""Leave out prompt text that does not apply to the turn's tools.

- The "Odysseus Terminus local-machine mode" rules were added whenever any
  selected tool was in the Terminus toolset. That set includes `ask_user` and
  `update_plan`, which every turn carries, so a plain question was told "the
  user referred to this computer … not ordinary chat". They now need a real
  file or shell tool.
- The date/time context names `manage_calendar` and `manage_tasks`. Those two
  lines are dropped when the tool is not offered this turn.

Both only remove text; with no tool selection (None, i.e. every tool) nothing
changes.
"""
from __future__ import annotations

from typing import Dict, Iterable, Optional

MACHINE_TOOLS = frozenset({
    "bash", "python", "read_file", "write_file", "edit_file", "apply_patch",
    "grep", "glob", "ls",
})

_DATETIME_TOOL_LINES = {
    "manage_calendar": "When scheduling calendar events with manage_calendar",
    "manage_tasks": "When scheduling a task with manage_tasks",
}


def wants_local_computer_rules(tool_names: Optional[Iterable[str]]) -> bool:
    return bool(tool_names) and bool(set(tool_names) & MACHINE_TOOLS)


def trim_datetime_message(message: Optional[Dict], tool_names: Optional[Iterable[str]]) -> Optional[Dict]:
    if not message or tool_names is None or not isinstance(message.get("content"), str):
        return message
    tools = set(tool_names)
    drop = [prefix for tool, prefix in _DATETIME_TOOL_LINES.items() if tool not in tools]
    if not drop:
        return message
    lines = [line for line in message["content"].split("\n")
             if not any(line.startswith(prefix) for prefix in drop)]
    return {**message, "content": "\n".join(lines)}
