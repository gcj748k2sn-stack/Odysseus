"""The ai-tidy reply parser — docs/todo.md item 44.

`/api/documents/ai-tidy` returned `500` on every logged call across 2026-07-30
and 08-01. Instrumentation and one live run found **two independent faults,
each hiding the other**:

  (a) `max_tokens=200` truncated the reply — `finish_reason=length chars=0`,
      settled by item 41's recorder rather than inferred.
  (b) **The model does not emit the JSON array the prompt asks for.** At a
      larger cap it finished cleanly and returned 295 characters of correct
      verdicts formatted ``0: keep\\n1: keep\\n2: keep…``, and the endpoint
      500'd anyway because the parser required ``[...]``.

**(b) is the one that mattered**: the endpoint would have kept failing on an
unlimited token budget, so "output appeared" was never going to mean "fixed".
This file covers (b). The cap is deliberately still 200 — the two fixes ship
separately so that a run which still fails names its own half.

⚠️ **This parser is an acting guard, not a reporting one** ([`CLAUDE.md`] §3):
its output decides which documents get ARCHIVED on a model's one-word verdict.
So the tests below lead with what it must NOT do — an unparseable reply must
yield nothing, and an index must never be inferred from a line's position.
An off-by-one here retires a document on another document's verdict.
"""

import pytest

from tests.helpers.import_state import clear_fake_database_modules

clear_fake_database_modules()

from routes.document_routes import _parse_tidy_verdicts as parse

# The reply as actually recorded, 2026-08-01 11:40:46, truncated at index 27
# of a 30-document batch. Kept verbatim: a fixture invented from the docstring
# would not have caught the format at all, which is how this ran for 3 days.
RECORDED = (
    "0: keep  \n1: keep  \n2: keep  \n3: keep  \n4: keep  \n5: junk  \n6: keep  \n"
    "7: junk  \n8: junk  \n9: junk  \n10: junk  \n11: junk  \n12: junk  \n13: junk  \n"
    "14: junk  \n15: keep  \n16: junk  \n17: junk  \n18: junk  \n19: junk  \n20: junk  \n"
    "21: junk  \n22: junk  \n23: junk  \n24: junk  \n25: junk  \n26: junk  \n27: junk"
)


# --------------------------------------------------------------------------
# Negative controls. Nothing parsed must mean nothing archived.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("reply", [
    "",
    "   \n  \n",
    None,
    "Okay, let me think about which of these documents are junk",
    "I reviewed the documents and they all look fine to me.",
    "[]",
    "[,]",
])
def test_unparseable_replies_yield_nothing(reply):
    """The caller raises 500 on `{}`, so an empty result is the safe failure.

    Without these a parser that returned a default verdict for every document
    would pass every positive test in this file — and would archive on a reply
    that said nothing at all.
    """
    assert parse(reply) == {}


def test_a_verdict_word_alone_is_not_a_verdict():
    """Prose containing "junk" must not be mistaken for a judgement.

    The line form is anchored and index-prefixed for exactly this reason.
    """
    assert parse("Some of these look like junk to me, especially the tests.") == {}
    assert parse("junk\nkeep\njunk") == {}


def test_an_unrecognised_verdict_word_is_dropped_not_guessed():
    """`12: maybe` leaves document 12 UNREVIEWED for the next run.

    Leaving it out is the safe direction: the caller's rule is "anything that
    isn't junk is keep", so admitting an unknown word here would silently mark
    a document reviewed on a verdict nobody understood.
    """
    assert parse("0: junk\n1: maybe\n2: keep") == {0: "junk", 2: "keep"}


# --------------------------------------------------------------------------
# The requested shape must keep working exactly as before.
# --------------------------------------------------------------------------

def test_json_array_is_still_mapped_positionally():
    """Regression control: the format the prompt asks for is unchanged.

    Positional mapping is the existing contract for this shape and is NOT
    changed by adding the line form.
    """
    assert parse('["keep","junk","keep"]') == {0: "keep", 1: "junk", 2: "keep"}


def test_json_array_survives_surrounding_prose():
    assert parse('Sure! Here you go:\n["junk","keep"]\nHope that helps.') == {0: "junk", 1: "keep"}


def test_json_wins_when_both_shapes_are_present():
    """The requested shape is tried first, so its semantics cannot be
    shadowed by a stray numbered line elsewhere in the reply."""
    assert parse('["keep","keep"]\n0: junk\n1: junk') == {0: "keep", 1: "keep"}


# --------------------------------------------------------------------------
# The shape the model actually produces.
# --------------------------------------------------------------------------

def test_the_recorded_reply_parses():
    """The 2026-08-01 11:40:46 reply — the one that 500'd."""
    got = parse(RECORDED)
    assert len(got) == 28
    assert got[0] == "keep"
    assert got[5] == "junk"
    assert got[15] == "keep"
    assert got[27] == "junk"
    # It stopped at 27 while finishing cleanly, so a 30-item batch is only
    # partly covered — the caller must leave 28 and 29 alone.
    assert 28 not in got and 29 not in got


@pytest.mark.parametrize("line,expected", [
    ("0: keep", {0: "keep"}),
    ("0. keep", {0: "keep"}),
    ("0) junk", {0: "junk"}),
    ("0 - junk", {0: "junk"}),
    ("  3:   KEEP  ", {3: "keep"}),
    ("12: Junk", {12: "junk"}),
])
def test_separator_and_case_variants(line, expected):
    assert parse(line) == expected


def test_index_is_taken_from_the_number_never_from_the_position():
    """The single most dangerous failure this parser could have.

    A reply that skips an index must leave that document untouched, not shift
    every later verdict onto its neighbour. Positional reading of this input
    would mark document 1 as junk on document 7's verdict, and this endpoint
    ARCHIVES on that value.
    """
    got = parse("0: keep\n7: junk\n9: junk")
    assert got == {0: "keep", 7: "junk", 9: "junk"}
    assert 1 not in got


def test_out_of_order_indices_are_honoured():
    assert parse("5: junk\n0: keep\n3: junk") == {0: "keep", 3: "junk", 5: "junk"}


def test_a_repeated_index_takes_the_last_word():
    """Not a designed feature — pinned so a change to it is deliberate."""
    assert parse("2: keep\n2: junk") == {2: "junk"}
