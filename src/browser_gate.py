"""Browser-tool gating helpers used by ``stream_agent_loop``.

Fork-only code moved out of ``src/agent_loop.py`` (smaller merge surface);
behaviour unchanged. Logs go to the ``src.agent_loop`` logger.
"""
import logging
from typing import Dict, Optional, Set

from src.tool_policy import BROWSER_SERVER_ID, BROWSER_TOOL_PREFIX

logger = logging.getLogger("src.agent_loop")


def _apply_browser_disable(disabled_tools: Set[str], mcp_disabled_map: Dict[str, set], mcp_mgr) -> bool:
    """Make builtin_browser in a disabled-tools list switch the whole server off.

    Downstream checks match exact tool names (mcp__builtin_browser__<tool>), so
    the server-wide token written by the admin panel, the can_use_browser
    privilege and manage_settings used to disable nothing. Expanding it here
    makes every check see the real names. Returns True when the browser is
    disabled this turn.
    """
    if BROWSER_SERVER_ID not in disabled_tools:
        return False
    names: Set[str] = set()
    if mcp_mgr:
        try:
            for tool in mcp_mgr.get_all_tools():
                if tool.get("server_id") == BROWSER_SERVER_ID and tool.get("name"):
                    names.add(tool["name"])
        except Exception as exc:
            logger.warning("Failed to enumerate browser MCP tools for disabling: %s", exc)
    disabled_tools.update(f"{BROWSER_TOOL_PREFIX}{name}" for name in names)
    if names:
        mcp_disabled_map.setdefault(BROWSER_SERVER_ID, set()).update(names)
    return True


def _browser_tool_names(mcp_mgr, disabled_map: Optional[Dict[str, set]] = None) -> Set[str]:
    """Qualified names of the connected browser tools that are not disabled."""
    if not mcp_mgr:
        return set()
    try:
        return {
            tool["qualified_name"]
            for tool in mcp_mgr.get_all_tools(disabled_map or {})
            if tool.get("server_id") == BROWSER_SERVER_ID
            and not tool.get("is_disabled")
            and tool.get("qualified_name")
        }
    except Exception as exc:
        logger.warning("Failed to list browser MCP tools: %s", exc)
        return set()


def _withhold_browser(disabled_map: Optional[Dict[str, set]], browser_names: Set[str]) -> Dict[str, set]:
    """Copy of ``disabled_map`` that also hides ``browser_names`` for one turn.

    The MCP schemas and the MCP prompt text are both built from this map, so
    one entry removes the browser from the native tool list, from the
    "local model" schema branch and from the text block that otherwise
    advertises tools the model was not given.
    """
    out = {k: set(v) for k, v in (disabled_map or {}).items()}
    out.setdefault(BROWSER_SERVER_ID, set()).update(
        name[len(BROWSER_TOOL_PREFIX):] for name in browser_names if name.startswith(BROWSER_TOOL_PREFIX)
    )
    return out
