"""Faithful Python port of the document editor's diff engine (static/js/document.js).

Exists so the diff/merge behaviour can be reasoned about offline — property-tested,
fuzzed, and replayed against recorded `document_versions` rows — without a browser.

Ported verbatim (same LCS table, same backtrack tie-breaks, same chunk grouping):
  _computeLineDiff        -> compute_line_diff
  _buildDiffChunks        -> build_diff_chunks
  _applyResolvedChunksToTextarea -> apply_resolved_chunks
  exitDiffMode merge branch      -> exit_diff_merge

Both apply functions now use one rule:

    chunk.resolved && !chunk.accepted  -> OLD   (an explicit rejection)
    everything else                    -> NEW   (accepted, or not yet reviewed)

An un-reviewed chunk keeps the NEW side because that is what the server already
holds. The original code inverted this — unresolved fell through to OLD — and
persisted the result on every click, which is what produced the "BLEND" rows in
app.db: `user` versions that resurrect previously-removed lines, match no stored
version byte-for-byte, and leave the document asserting both the pre-edit and
post-edit text for the same section.

`exit_diff_merge` is kept as a separate function because the original had two
subtly different conditions in these two places; they now agree, and a property
test pins that agreement.
"""

from dataclasses import dataclass, field
from typing import List, Literal, Optional

DIFF_MODE_THRESHOLD = 3  # min changed lines to trigger diff mode (document.js:8344)

EntryType = Literal["equal", "insert", "delete"]


@dataclass
class Entry:
    type: EntryType
    line: str


@dataclass
class Chunk:
    id: int
    old_lines: List[str]
    new_lines: List[str]
    start_line: int
    resolved: bool = False
    accepted: bool = False


def compute_line_diff(old_text: str, new_text: str) -> List[Entry]:
    """LCS diff, matching document.js:8361 including its backtrack tie-break."""
    old_lines = old_text.split("\n")
    new_lines = new_text.split("\n")
    m, n = len(old_lines), len(new_lines)

    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        oi = old_lines[i - 1]
        row, prev = dp[i], dp[i - 1]
        for j in range(1, n + 1):
            row[j] = prev[j - 1] + 1 if oi == new_lines[j - 1] else max(prev[j], row[j - 1])

    entries: List[Entry] = []
    i, j = m, n
    while i > 0 or j > 0:
        if i > 0 and j > 0 and old_lines[i - 1] == new_lines[j - 1]:
            entries.append(Entry("equal", old_lines[i - 1]))
            i -= 1
            j -= 1
        elif j > 0 and (i == 0 or dp[i][j - 1] >= dp[i - 1][j]):
            entries.append(Entry("insert", new_lines[j - 1]))
            j -= 1
        else:
            entries.append(Entry("delete", old_lines[i - 1]))
            i -= 1
    entries.reverse()
    return entries


def build_diff_chunks(entries: List[Entry]) -> List[Chunk]:
    """Group entries into contiguous change blocks (document.js:_buildDiffChunks)."""
    chunks: List[Chunk] = []
    chunk_id = 0
    line_idx = 0
    i = 0
    while i < len(entries):
        if entries[i].type == "equal":
            line_idx += 1
            i += 1
        else:
            start_line = line_idx
            old_lines: List[str] = []
            new_lines: List[str] = []
            while i < len(entries) and entries[i].type != "equal":
                (old_lines if entries[i].type == "delete" else new_lines).append(entries[i].line)
                i += 1
            chunks.append(Chunk(chunk_id, old_lines, new_lines, start_line))
            chunk_id += 1
            line_idx += len(old_lines) + len(new_lines)
    return chunks


def _walk(entries: List[Entry], chunks: List[Chunk], use_new) -> str:
    """Shared body of both apply functions. `use_new(chunk) -> bool`.

    NOTE the positional coupling: chunks are indexed by order of appearance in
    `entries`. If `chunks` was built from a DIFFERENT entries list than the one
    being walked (the stale-singleton case), decisions land on the wrong chunks
    and the result can mix generations. That is the failure mode under test.
    """
    result: List[str] = []
    chunk_idx = 0
    i = 0
    while i < len(entries):
        if entries[i].type == "equal":
            result.append(entries[i].line)
            i += 1
        else:
            chunk = chunks[chunk_idx] if chunk_idx < len(chunks) else None
            chunk_idx += 1
            chunk_old: List[str] = []
            chunk_new: List[str] = []
            while i < len(entries) and entries[i].type != "equal":
                (chunk_old if entries[i].type == "delete" else chunk_new).append(entries[i].line)
                i += 1
            result.extend(chunk_new if (chunk and use_new(chunk)) else chunk_old)
    return "\n".join(result)


def _keeps_new(chunk: Chunk) -> bool:
    """Only an explicit rejection reverts a chunk to its old side."""
    return not (chunk.resolved and not chunk.accepted)


def apply_resolved_chunks(old_text: str, new_text: str, chunks: List[Chunk]) -> str:
    """_applyResolvedChunksToTextarea — live preview during review."""
    return _walk(compute_line_diff(old_text, new_text), chunks, _keeps_new)


def exit_diff_merge(old_text: str, new_text: str, chunks: List[Chunk]) -> str:
    """exitDiffMode(discard=false) — the content committed when review ends."""
    return _walk(compute_line_diff(old_text, new_text), chunks, _keeps_new)


def changed_lines(a: str, b: str) -> int:
    """Positional changed-line count — the DIFF_MODE_THRESHOLD test in handleDocUpdate."""
    al, bl = a.split("\n"), b.split("\n")
    return sum(
        1
        for i in range(max(len(al), len(bl)))
        if (al[i] if i < len(al) else None) != (bl[i] if i < len(bl) else None)
    )


# --------------------------------------------------------------------------
# Editor state machine
# --------------------------------------------------------------------------

@dataclass
class Editor:
    """The subset of document.js state that decides what gets PUT to the server."""

    textarea: str = ""
    server: str = ""
    diff_active: bool = False
    diff_old: Optional[str] = None
    diff_new: Optional[str] = None
    chunks: List[Chunk] = field(default_factory=list)
    saves: List[str] = field(default_factory=list)
    persist_on_ai_teardown: bool = False  # True = pre-fix behaviour

    def _save(self) -> None:
        self.server = self.textarea
        self.saves.append(self.textarea)

    def enter_diff(self, old: str, new: str) -> None:
        if self.diff_active:
            self.exit_diff(discard=True, persist=self.persist_on_ai_teardown)
        entries = compute_line_diff(old, new)
        chunks = build_diff_chunks(entries)
        if not chunks:
            return
        self.diff_active, self.diff_old, self.diff_new, self.chunks = True, old, new, chunks

    def exit_diff(self, discard: bool, persist: bool = True) -> None:
        if not self.diff_active:
            return
        self.diff_active = False
        if persist:
            if discard:
                self.textarea = self.diff_old or ""
            else:
                self.textarea = exit_diff_merge(self.diff_old or "", self.diff_new or "", self.chunks)
            self._save()
        self.diff_old = self.diff_new = None
        self.chunks = []

    def handle_doc_update(self, content: str) -> None:
        """AI edit lands. Mirrors handleDocUpdate's ordering exactly."""
        if self.diff_active:
            self.exit_diff(discard=True, persist=self.persist_on_ai_teardown)
        self.server = content
        old_content = self.textarea
        if old_content and old_content != content:
            if changed_lines(old_content, content) >= DIFF_MODE_THRESHOLD:
                self.enter_diff(old_content, content)
            else:
                self.textarea = content
        else:
            self.textarea = content

    def resolve_chunk(self, chunk_id: int, accept: bool) -> None:
        """_resolveChunk — updates the buffer only; the review commits when it ends."""
        chunk = next((c for c in self.chunks if c.id == chunk_id), None)
        if not chunk or chunk.resolved:
            return
        chunk.resolved, chunk.accepted = True, accept
        self.textarea = apply_resolved_chunks(self.diff_old or "", self.diff_new or "", self.chunks)
        if all(c.resolved for c in self.chunks):
            self.exit_diff(discard=False, persist=True)
