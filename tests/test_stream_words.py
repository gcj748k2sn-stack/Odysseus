"""The repetition guard reads words across deltas and keeps numbers.

Covers ``src/stream_words.py`` and its call site in
``_DegenerateStreamGuard.check`` (``src/llm_core.py``). The stream is fed the
way local servers send it: one sub-word token per delta, the same word always
split the same way.
"""
import re

import pytest

from src.llm_core import _DegenerateStreamGuard
from src.stream_words import MAX_CARRY_CHARS, WordStream

NODES = ["climalog-1", "climalog-2", "martha9"]
_SPLIT = {"climalog": ["cl", "imal", "og"], "martha": ["mar", "tha"], "recheck": ["rec", "heck"]}


def _deltas(text):
    out = []
    for tok in re.findall(r"[A-Za-z]+|\d|[^\sA-Za-z\d]|\s+", text):
        out += _SPLIT.get(tok.lower(), [tok])
    return out


def _fires(text):
    guard = _DegenerateStreamGuard("m")
    return any(guard.check(d) for d in _deltas(text))


_CSV = [f"2026-09-01T{6 + 2 * (i // 3):02d}:00,{NODES[i % 3]},21.{i % 10},48.{i % 7}" for i in range(36)]


@pytest.mark.parametrize("name, text", [
    ("restating the CSV while counting", "Let me count the rows.\n" + "\n".join(_CSV)),
    ("numbered rows", "Counting: " + " ".join(f"row {i + 1}," for i in range(36))),
    ("numbered node names", "\n".join(f"{i + 1}. {NODES[i % 3]}" for i in range(36))),
    ("the node column", "Nodes in order: " + ", ".join(NODES[i % 3] for i in range(36))),
    ("prose", "The file has a header and then data rows. I will count them and answer with the number."),
])
def test_legitimate_enumeration_is_not_a_loop(name, text):
    assert not _fires(text), name


@pytest.mark.parametrize("name, text", [
    ("phrase loop", "Wait, let me recheck. " * 40),
    ("token loop", "Var " * 60),
    ("token loop without spaces", "Var" * 200),
    ("numbered loop that repeats exactly", "row 1, " * 60),
    ("one delta", "repeat " * 100),
])
def test_real_loops_still_stop(name, text):
    if name in ("token loop without spaces", "one delta"):
        guard = _DegenerateStreamGuard("m")
        pieces = ["Var"] * 200 if "spaces" in name else [text]
        assert any(guard.check(p) for p in pieces), name
    else:
        assert _fires(text), name


def test_words_are_joined_across_deltas():
    w = WordStream()
    assert w.feed("cl") == [] and w.feed("imal") == [] and w.feed("og") == []
    assert w.feed("-1, ") == ["climalog", "1"]
    assert w.feed("martha9 x") == ["martha9"]
    assert w.feed("") == []


def test_a_word_without_end_is_released_as_it_came():
    w = WordStream()
    got = []
    for _ in range(MAX_CARRY_CHARS):
        got += w.feed("ab")
    assert got and set(got) == {"ab"}
