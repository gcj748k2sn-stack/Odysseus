"""Wiring: a path-bound workspace no longer forces bash on.

A structural check by design (CLAUDE.md §4, wiring tests): the branch sits in
the middle of ``chat_stream``, which a behaviour test can only reach through
the whole route. Behaviour of ``bash_setting`` itself is in
``test_message_path_workspace.py``.
"""

import inspect
import re

from routes import chat_routes


def _auto_workspace_branch() -> str:
    source = inspect.getsource(chat_routes)
    start = source.index("_auto_workspace, _ = _resolve_workspace_from_message_path(")
    end = source.index('"chat→agent auto-escalation: explicit path workspace=%s"', start)
    return source[start:end]


def test_bash_follows_bash_setting_in_the_path_branch():
    branch = _auto_workspace_branch()
    assert "allow_bash = _message_path_workspace.bash_setting(message, allow_bash)" in branch
    assert not re.search(r'allow_bash\s*=\s*"true"', branch), branch
