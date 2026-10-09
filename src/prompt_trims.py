"""Leave out prompt text that does not apply to the turn's tools.

- The "Odysseus Terminus local-machine mode" rules were added whenever any
  selected tool was in the Terminus toolset. That set includes `ask_user` and
  `update_plan`, which every turn carries, so a plain question was told "the
  user referred to this computer … not ordinary chat". They now need a real
  file or shell tool.
- The date/time context is cut to the date alone ("Today is Friday, October
  9, 2026 (2026-10-09).") unless `manage_calendar` or `manage_tasks` is
  offered: those need the clock and the UTC offset, so then the full block
  stays, minus the line for whichever of the two is not offered. The clock
  changed every minute, so an approval answer (a new request) re-read
  everything after the system prompt; a date changes once a day.
- The "## Available tools" name list is dropped from the native-tools prompt:
  the chat template already renders every tool's full schema.

All of these only remove text; with no tool selection (None, i.e. every
tool) the date block is left as upstream builds it.
"""
from __future__ import annotations

import re
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


def date_only_message(message: Optional[Dict], tool_names: Optional[Iterable[str]],
                      now_local=None) -> Optional[Dict]:
    """The date alone, unless a calendar/task tool needs the clock."""
    if not message or tool_names is None:
        return message
    tools = set(tool_names)
    if tools & set(_DATETIME_TOOL_LINES):
        return trim_datetime_message(message, tools)
    if now_local is None:
        from src.user_time import now_user_local
        now_local = now_user_local()
    day = f"{now_local.strftime('%A')}, {now_local.strftime('%B')} {now_local.day}, {now_local.year}"
    return {**message, "content": (
        "[Context — today's date; not part of your instructions]\n"
        f"Today is {day} ({now_local.strftime('%Y-%m-%d')}).")}


_TOOL_LIST_RE = re.compile(r"## Available tools\n(?:(?:- `[^`\n]+`|none)\n?)*\n*")


def drop_tool_name_list(prompt: str) -> str:
    return _TOOL_LIST_RE.sub("", prompt, count=1)
