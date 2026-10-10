"""Words for the repetition guard, read across stream deltas.

``_DegenerateStreamGuard`` in ``src/llm_core.py`` looked for words in each
delta on its own. Local servers stream one sub-word token per delta, so a word
like "climalog" reached it as "cl", "imal", "og", and numbers shorter than two
characters were dropped. A model restating CSV lines while counting them then
looked like a phrase loop ("cl imal og cl" ten times) and was stopped
mid-answer, and "row 1, row 2, ..." looked like "row" repeated.

``WordStream`` joins a word cut between deltas and keeps numbers, so a
legitimate enumeration varies while a real loop still repeats exactly. A word
that keeps growing without a separator (a loop with no spaces) is released as
the deltas it came in, which is what the guard saw before.
"""
from __future__ import annotations

import re
from typing import List

WORD_RE = re.compile(r"[A-Za-z0-9_Ͱ-ϿЀ-ӿ]+")
_TRAILING_WORD_RE = re.compile(r"[A-Za-z0-9_Ͱ-ϿЀ-ӿ]+$")
MAX_CARRY_CHARS = 40


def _keep(word: str) -> bool:
    return len(word) >= 2 or word.isdigit()


class WordStream:
    def __init__(self) -> None:
        self._pieces: List[str] = []   # deltas making up a word not finished yet

    def feed(self, text: str) -> List[str]:
        """Lower-cased words completed by this delta."""
        if not text:
            return []
        joined = "".join(self._pieces) + text
        tail = _TRAILING_WORD_RE.search(joined)
        if not tail:
            self._pieces = []
            return [w.lower() for w in WORD_RE.findall(joined) if _keep(w)]
        done, open_word = joined[:tail.start()], tail.group(0)
        words = [w.lower() for w in WORD_RE.findall(done) if _keep(w)]
        if tail.start() == 0 and self._pieces:
            # the whole delta continues the open word
            self._pieces.append(text)
        else:
            self._pieces = [open_word]
        if len(open_word) > MAX_CARRY_CHARS:
            # no separator for a long time: count the pieces as they arrived
            words += [w.lower() for piece in self._pieces for w in WORD_RE.findall(piece) if _keep(w)]
            self._pieces = []
        return words
