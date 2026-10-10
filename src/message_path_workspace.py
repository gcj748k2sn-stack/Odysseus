"""Bind a workspace from a path the user typed (fork module).

Upstream bound a path only when the message also held one of a fixed list of
task words ("file", "read", "run", ...), and kept a trailing "?" on the path.
So "What is the first heading in /Users/me/repo/README.md?" bound nothing, the
turn got no file tools, and the model said it could not read the file (notes:
"A file path in a message without a workspace gets no file tools").

Here the signal is the path itself: it must exist on disk and pass
``vet_workspace`` (no sensitive paths, no app state, no filesystem root). A file
binds its parent directory, a directory binds itself.

Upstream also switched bash on for every such bind. ``bash_setting`` keeps that
only for messages that ask for an action (run, build, convert, ...); a question
about a file leaves the request's own bash setting alone.
"""
from __future__ import annotations

import os
import re
from typing import List, Optional

# A path starts at the beginning, after whitespace, or after an opening quote,
# backtick or bracket - never inside a URL ("http://host/x") or a word ("and/or").
_PATH_RE = re.compile(r"(?<![^\s\"'`(\[])(~?/[^\"'\s`<>]+)")
# Sentence punctuation and closing quotes/brackets glued to the end of a path.
_TRAILING = ".,;:!?)]}\"'`"

# Words that ask for an action on the machine. Upstream's list minus the words
# that only name or read something (file, folder, path, repo, open, read, ...).
_SHELL_ACTION_RE = re.compile(
    r"\b(?:movie|video|subtitles?|srt|vtt|ass|download|save|rename|move|copy|"
    r"extract|convert|ffmpeg|run|execute|fix|debug|test|build|install|compile)\b",
    re.IGNORECASE,
)


def candidate_paths(message: Optional[str]) -> List[str]:
    """Absolute or ~ paths in the message, trailing punctuation removed."""
    out = []
    for match in _PATH_RE.finditer(str(message or "")):
        raw = match.group(1).rstrip(_TRAILING)
        if raw:
            out.append(raw)
    return out


def resolve(message: Optional[str]) -> str:
    """The workspace to bind for the first usable path, or ""."""
    from src.tool_execution import vet_workspace

    for raw in candidate_paths(message):
        expanded = os.path.realpath(os.path.expanduser(raw))
        if os.path.isfile(expanded):
            candidate = os.path.dirname(expanded)
        elif os.path.isdir(expanded):
            candidate = expanded
        else:
            continue
        workspace = vet_workspace(candidate) or ""
        if workspace:
            return workspace
    return ""


def bash_setting(message: Optional[str], current):
    """Return "true" when the message asks for an action, else ``current``.

    Paths are removed first, so a folder named "build" or "test" in the path
    does not count as a request.
    """
    words = _PATH_RE.sub(" ", str(message or ""))
    if _SHELL_ACTION_RE.search(words):
        return "true"
    return current
