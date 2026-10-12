"""The line-number gutter a model copies into an edit_document block.

The active-document context shows each line as "<number><TAB><text>" so the
model can find lines. Weaker models copy that gutter into FIND, and
``edit_document`` already retries FIND without it. They copy it into REPLACE
too, and that text was written into the document as is: "3\\t- map" instead of
"- map", which silently broke a list in the benchmark. When FIND only matched
without the gutter, the same gutter is taken off REPLACE.
"""
from __future__ import annotations

import re

_GUTTER = re.compile(r"^\d+\t", re.M)


def strip(text: str) -> str:
    """Remove a leading "<digits><TAB>" from every line."""
    return _GUTTER.sub("", text or "")
