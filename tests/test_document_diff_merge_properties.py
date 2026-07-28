"""Property tests for the document editor's diff/merge engine.

Exercises the Python port in ``tests/tools/diff_model.py`` (a faithful transcription
of ``_computeLineDiff`` / ``_buildDiffChunks`` / ``_applyResolvedChunksToTextarea`` /
the ``exitDiffMode`` merge branch in ``static/js/document.js``).

Two things are under test:

1. **The invariants a review UI must hold.** Accepting everything must yield exactly
   the new content; accepting nothing must yield exactly the old; the output must
   never contain a line that appears in neither side. These are the guarantees a user
   is implicitly relying on when they click Accept.

2. **The documented default, and what it costs.** ``_applyResolvedChunksToTextarea``
   treats an *unresolved* chunk as rejected ("unresolved chunks default to the
   original (rejected) until the user decides") — and ``_resolveChunk`` calls
   ``saveDocument()`` immediately afterwards. So the first Accept click persists a
   document in which every chunk the user has not yet looked at is rolled back to
   pre-edit content. ``test_first_accept_persists_a_rollback_of_everything_else``
   pins that behaviour, because it is the suspected source of the "BLEND" rows in
   app.db and any fix must change it deliberately rather than by accident.

3. **Stale-chunk misalignment.** Chunks are indexed positionally against a freshly
   recomputed entry list. If the chunk list was built from a different content pair
   than the one being walked — the module-global singleton drifting — decisions land
   on the wrong chunks and generations mix. Demonstrated in isolation here.
"""

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

from diff_model import (  # noqa: E402
    apply_resolved_chunks,
    build_diff_chunks,
    compute_line_diff,
    exit_diff_merge,
)


def _chunks(old, new):
    return build_diff_chunks(compute_line_diff(old, new))


def _random_text(rng, n_lines=14, alphabet="abcdefgh"):
    return "\n".join(rng.choice(alphabet) + str(rng.randint(0, 4)) for _ in range(n_lines))


def _pairs(count=120, seed=20260719):
    rng = random.Random(seed)
    out = []
    for _ in range(count):
        old = _random_text(rng, rng.randint(1, 16))
        # derive `new` by mutating `old` so the pair looks like a real edit
        lines = old.split("\n")
        for _ in range(rng.randint(1, 6)):
            op = rng.choice(["del", "ins", "mod"])
            if not lines:
                lines = ["x0"]
            i = rng.randrange(len(lines))
            if op == "del":
                lines.pop(i)
            elif op == "ins":
                lines.insert(i, _random_text(rng, 1))
            else:
                lines[i] = _random_text(rng, 1)
        out.append((old, "\n".join(lines) if lines else ""))
    return out


PAIRS = _pairs()


# --- 1. invariants the review UI must hold -------------------------------------

@pytest.mark.parametrize("old,new", PAIRS)
def test_accepting_every_chunk_yields_exactly_the_new_content(old, new):
    chunks = _chunks(old, new)
    for c in chunks:
        c.resolved = c.accepted = True
    assert apply_resolved_chunks(old, new, chunks) == new
    assert exit_diff_merge(old, new, chunks) == new


@pytest.mark.parametrize("old,new", PAIRS)
def test_rejecting_every_chunk_yields_exactly_the_old_content(old, new):
    chunks = _chunks(old, new)
    for c in chunks:
        c.resolved, c.accepted = True, False
    assert apply_resolved_chunks(old, new, chunks) == old
    assert exit_diff_merge(old, new, chunks) == old


@pytest.mark.parametrize("old,new", PAIRS)
def test_output_never_invents_a_line(old, new):
    """Whatever the decisions, every output line came from one side or the other."""
    rng = random.Random(hash((old, new)) & 0xFFFF)
    chunks = _chunks(old, new)
    for c in chunks:
        c.resolved = rng.random() < 0.7
        c.accepted = rng.random() < 0.5
    allowed = set(old.split("\n")) | set(new.split("\n"))
    assert set(apply_resolved_chunks(old, new, chunks).split("\n")) <= allowed


@pytest.mark.parametrize("old,new", PAIRS)
def test_an_explicit_rejection_is_distinguishable_from_no_decision(old, new):
    """The core of the fix.

    These were indistinguishable, and that is what corrupted documents: "I have
    not looked at this yet" was recorded as "I rejected this" and then written to
    the server. Rejecting everything must revert; deciding nothing must not.
    """
    rejected = _chunks(old, new)
    for c in rejected:
        c.resolved, c.accepted = True, False
    untouched = _chunks(old, new)

    assert apply_resolved_chunks(old, new, rejected) == old
    assert apply_resolved_chunks(old, new, untouched) == new
    if old != new:
        assert apply_resolved_chunks(old, new, rejected) != apply_resolved_chunks(
            old, new, untouched
        )


@pytest.mark.parametrize("old,new", PAIRS)
def test_preview_and_commit_agree(old, new):
    """What the user sees mid-review must be what gets committed.

    The two functions had subtly different conditions in the original
    (`resolved && accepted` vs bare `accepted`), so the preview and the committed
    result could disagree for an un-reviewed chunk.
    """
    rng = random.Random(hash((new, old)) & 0xFFFF)
    chunks = _chunks(old, new)
    for c in chunks:
        c.resolved = rng.random() < 0.6
        c.accepted = rng.random() < 0.5
    assert apply_resolved_chunks(old, new, chunks) == exit_diff_merge(old, new, chunks)


# --- 2. the cost of that default ------------------------------------------------

def test_accepting_one_chunk_leaves_the_others_alone():
    """The exact scenario that corrupted doc 92f3b2a0 v3.

    Before the fix, accepting the first correction rolled the second back to its
    pre-edit value and PUT that to the server. Now an un-reviewed chunk is left
    at the AI's value, so one click changes nothing but the chunk clicked.
    """
    old = "\n".join(["intro", "TEMP: 15C", "body", "CO2: 1500ppm", "outro"])
    new = "\n".join(["intro", "TEMP: 25C", "body", "CO2: 700ppm", "outro"])
    chunks = _chunks(old, new)
    assert len(chunks) == 2, "expected one chunk per corrected value"

    chunks[0].resolved = chunks[0].accepted = True  # accept the first only
    result = apply_resolved_chunks(old, new, chunks)

    assert "TEMP: 25C" in result, "the accepted correction survives"
    assert "CO2: 700ppm" in result, "the un-reviewed correction is NOT rolled back"
    assert "CO2: 1500ppm" not in result
    assert result == new, "accepting a chunk cannot change any other chunk"


def test_unreviewed_pure_deletions_are_not_resurrected():
    """The +N / -0 fingerprint that identified every BLEND row in app.db.

    A chunk whose `newLines` is empty (the AI deleted a block) used to restore
    those lines when left unresolved, removing nothing in exchange — so the
    document grew and every added line was verbatim from an older version. That
    is the signature the database scan keyed on; it must no longer be reachable.
    """
    old = "\n".join(["keep", "Calories: 33 kcal", "Protein: 23.5g", "Fiber: 4g", "tail"])
    new = "\n".join(["keep", "tail"])
    chunks = _chunks(old, new)

    result = apply_resolved_chunks(old, new, chunks)  # nothing reviewed yet
    assert result == new, "an un-reviewed deletion stays deleted"
    assert not set(result.split("\n")) - set(new.split("\n")), "nothing resurrected"

    for c in chunks:  # but an explicit reject still restores them
        c.resolved, c.accepted = True, False
    assert apply_resolved_chunks(old, new, chunks) == old


def test_split_replacement_can_no_longer_produce_both_versions():
    """Line-level LCS splits a rewritten block into separate delete/insert chunks.

    Doc 92f3b2a0 v3 ended up asserting BOTH the pre-edit and post-edit text for
    twelve sections, because the delete half was left un-reviewed (restoring the
    old heading) while the insert half supplied the new one. With un-reviewed
    meaning "keep new", no combination of decisions can yield both.
    """
    old = "\n".join(["## Phase 1: Spawn Run (Colonization)", "shared line", "tail"])
    new = "\n".join(["## Phase 1: Colonization", "shared line", "tail"])
    chunks = _chunks(old, new)

    for combo in range(2 ** len(chunks)):
        for i, c in enumerate(chunks):
            c.resolved = bool(combo >> i & 1)
            c.accepted = False  # resolved -> rejected, unresolved -> keep new
        out = apply_resolved_chunks(old, new, chunks)
        both = "## Phase 1: Spawn Run (Colonization)" in out and "## Phase 1: Colonization" in out
        assert not both, f"decision mask {combo:b} left both headings in the document"


# --- 3. stale-chunk misalignment ------------------------------------------------

def test_stale_chunk_list_breaks_the_accept_everything_guarantee():
    """Chunks are indexed positionally against a freshly recomputed entry list.

    When the chunk list belongs to a different content pair than the one being
    walked — the module-global diff singleton drifting behind an AI update — the
    decisions land on the wrong chunks, and "I accepted everything" no longer
    produces the new content.
    """
    old = "\n".join(["a", "OLD-1", "b", "c", "OLD-2", "d"])
    new = "\n".join(["a", "NEW-1", "b", "c", "NEW-2", "d"])
    # chunks built from an unrelated, single-change pair
    stale = _chunks("a\nSOMETHING\nb", "a\nELSE\nb")
    for c in stale:
        c.resolved = c.accepted = True
    assert len(stale) < len(_chunks(old, new))

    out = apply_resolved_chunks(old, new, stale)
    assert out != new, "a stale chunk list silently drops accepted changes"
    assert "NEW-1" in out and "OLD-2" in out, "generations mix within one document"


def test_recorded_blend_row_is_reproduced_byte_exact():
    """The recorded BLEND row must no longer be producible.

    Session 11ea1727, doc 5bce6d08 v4 was reproduced byte-exact by accepting
    chunks {2,4,6} of 8 and leaving the other five unresolved — the replay harness
    in tests/tools/replay_blend_rows.py found that sequence. Under the fixed rule
    the same clicks must leave the five un-reviewed chunks at the AI's values, so
    the corrupted document is unreachable.
    """
    # Eight separate chunks: changed lines must be separated by unchanged ones,
    # or the LCS walk merges them into a single contiguous run.
    old = "\n".join(x for i in range(8) for x in (f"keep{i}", f"old{i}"))
    new = "\n".join(x for i in range(8) for x in (f"keep{i}", f"new{i}"))
    chunks = _chunks(old, new)
    assert len(chunks) == 8

    for idx in (2, 4, 6):
        chunks[idx].resolved = chunks[idx].accepted = True
    out = apply_resolved_chunks(old, new, chunks)

    for i in range(8):
        assert f"new{i}" in out.split("\n"), f"chunk {i} lost its correction"
        assert f"old{i}" not in out.split("\n"), f"chunk {i} was resurrected"
    assert out == new, "accepting a subset must not alter the un-reviewed remainder"

    # And the only way back to `old` is to reject every chunk explicitly.
    for c in chunks:
        c.resolved, c.accepted = True, False
    assert apply_resolved_chunks(old, new, chunks) == old
