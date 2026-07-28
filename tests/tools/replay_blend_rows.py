"""Search editor operation sequences that reproduce the recorded BLEND versions.

A "BLEND" is a client-written (`source="user"`) document version that resurrects
lines removed by earlier AI edits, adds no novel text, and is byte-identical to no
stored version. The hypothesis under test:

    they are produced by the accept/deny review UI — `_resolveChunk` persists a
    state in which every not-yet-decided chunk is rolled back to pre-edit content,
    against a diff whose old side is itself an unpersisted intermediate.

Byte-exact reproduction of a recorded row is near-proof. Failure to reproduce means
the hypothesis is wrong or incomplete for that row, and must not be recorded as the
mechanism — a discipline these docs have had to learn three times.

The search is a DFS over the editor state machine: at every diff that opens, try
every subset of chunks the user might have accepted (leaving the rest unresolved,
which is what the UI defaults to), then let the next AI update land, and recurse.
Every intermediate save is compared, not just the final one, since the backend
coalesces consecutive `user` writes within 60s into one row.

Usage:  python3 tests/tools/replay_blend_rows.py [path/to/app.db]
"""

import itertools
import sqlite3
import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diff_model import Editor  # noqa: E402

MAX_CHUNKS_PER_STAGE = 12   # 2**12 subsets is the practical ceiling per stage
NODE_BUDGET = 400_000       # abort a row rather than run unbounded


class Budget(Exception):
    pass


def _subsets(n):
    for r in range(n + 1):
        for combo in itertools.combinations(range(n), r):
            yield combo


def search(ai_versions, target, persist):
    """DFS over (chunk decisions, AI updates). Returns a description or None."""
    nodes = [0]
    trail = []

    def recurse(ed, remaining):
        nodes[0] += 1
        if nodes[0] > NODE_BUDGET:
            raise Budget()
        if target in ed.saves:
            return " -> ".join(trail) if trail else "no user interaction"

        if ed.diff_active and len(ed.chunks) <= MAX_CHUNKS_PER_STAGE:
            n = len(ed.chunks)
            for combo in _subsets(n):
                branch = deepcopy(ed)
                for cid in combo:
                    branch.resolve_chunk(cid, True)
                trail.append(f"accept {list(combo) or 'none'} of {n}")
                if target in branch.saves:
                    return " -> ".join(trail)
                if remaining:
                    nxt = deepcopy(branch)
                    nxt.handle_doc_update(remaining[0])
                    hit = recurse(nxt, remaining[1:])
                    if hit:
                        return hit
                trail.pop()
        elif remaining:
            nxt = deepcopy(ed)
            nxt.handle_doc_update(remaining[0])
            trail.append("(no diff open)")
            hit = recurse(nxt, remaining[1:])
            if hit:
                return hit
            trail.pop()
        return None

    ed = Editor(persist_on_ai_teardown=persist)
    ed.textarea = ed.server = ai_versions[0]
    try:
        if len(ai_versions) > 1:
            ed.handle_doc_update(ai_versions[1])
            return recurse(ed, ai_versions[2:])
        return recurse(ed, [])
    except Budget:
        return f"ABORTED after {NODE_BUDGET} nodes (search space too large)"


def stage_shape(ai_versions, persist):
    """Report how many chunks each diff opens with — diagnostics for the search."""
    ed = Editor(persist_on_ai_teardown=persist)
    ed.textarea = ed.server = ai_versions[0]
    shape = []
    for v in ai_versions[1:]:
        ed.handle_doc_update(v)
        shape.append(len(ed.chunks) if ed.diff_active else 0)
    return shape


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else "data/app.db"
    conn = sqlite3.connect(db)
    docs = {}
    for did, sid in conn.execute("select id, session_id from documents"):
        vs = list(conn.execute(
            "select version_number, source, content from document_versions "
            "where document_id=? order by version_number", (did,)))
        if len(vs) >= 2:
            docs[did] = (sid, vs)
    print(f"loaded {len(docs)} documents from {db}\n")

    for did, (sid, vs) in docs.items():
        by = {v: c for v, _s, c in vs}
        for idx, (v, src, content) in enumerate(vs):
            if src != "user" or idx == 0:
                continue
            if any(w < v and by[w] == content for w in by):
                continue  # REVERT, not BLEND
            prev = vs[idx - 1][2]
            added = [l for l in set(content.split("\n")) - set(prev.split("\n")) if l.strip()]
            if not added:
                continue
            if any(not any(w < v and l in by[w].split("\n") for w in by) for l in added):
                continue  # novel text -> genuine user edit
            ai = [c for vv, s, c in vs if vv < v and s == "ai"]
            print(f"BLEND  session {str(sid)[:8]}  doc {did[:8]}  v{v}  "
                  f"(+{len(added)} resurrected lines, {len(ai)} preceding AI versions)")
            print(f"    chunks opened per AI update: {stage_shape(ai, False)}")
            for persist in (False, True):
                label = "post-fix (persist=False)" if not persist else "pre-fix  (persist=True) "
                hit = search(ai, content, persist)
                print(f"    {label}: {hit if hit else 'NO SEQUENCE REPRODUCES THIS'}")
            print()


if __name__ == "__main__":
    main()
