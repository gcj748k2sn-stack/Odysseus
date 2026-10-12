"""Fit a web_search result into the tool-output limit without cutting its end
(fork module).

comprehensive_web_search returns: sources list and results summary (head),
fetched page blocks "[CONTENT n] From: …" (middle), and an end marker plus
"IMPORTANT INSTRUCTIONS … answer the user's question" (tail). A plain
`text[:limit]` cut the tail off whenever the pages were long, so the model got
a result that ended mid-sentence with no instruction to answer the question —
and a 9B model then "completed" a snippet instead of answering (notes entry "A relevance filter for web results",
"Search output cut at 10,000 characters").

Here the page blocks are shortened evenly at line or sentence boundaries and
head and tail are kept whole. Text without the expected markers falls back to
the old plain cut.
"""
import re

PAGES_MARKER = "\nFETCHED PAGE CONTENT:"
END_MARKER = "\n" + "=" * 70 + "\nEND OF WEB SEARCH RESULTS"
BLOCK_RE = re.compile(r"(?=\n\[CONTENT(?: \d+)?\] From: )")
SHORTENED = " […page text shortened to fit]"
MIN_BLOCK = 200


def _cut(block, size):
    """`block` cut to at most `size` chars, at a line or sentence end when one is near."""
    if len(block) <= size:
        return block
    room = max(size - len(SHORTENED), 0)
    piece = block[:room]
    for sep in ("\n", ". "):
        pos = piece.rfind(sep)
        if pos >= room * 0.6:
            piece = piece[:pos + (1 if sep == ". " else 0)]
            break
    return piece.rstrip() + SHORTENED


def fit_search_output(text, limit):
    """`text` if it fits, else a version of at most `limit` chars that keeps the
    head and the closing instructions and shortens the fetched pages."""
    if len(text) <= limit:
        return text
    start = text.find(PAGES_MARKER)
    end = text.rfind(END_MARKER)
    if start < 0 or end < start:
        return text[:limit]
    head_end = text.find("\n", start + len(PAGES_MARKER))
    head_end = text.find("\n", head_end + 1) if head_end >= 0 else -1     # keep the "-----" rule
    if head_end < 0 or head_end > end:
        return text[:limit]
    head, middle, tail = text[:head_end], text[head_end:end], text[end:]
    budget = limit - len(head) - len(tail)
    blocks = [b for b in BLOCK_RE.split(middle) if b]
    if budget < MIN_BLOCK or not blocks:
        # Not even the pages' headers fit: drop the pages, keep the end.
        keep = max(limit - len(tail) - len(SHORTENED), 0)
        return (text[:keep] + SHORTENED + tail)[:limit] if keep else tail[-limit:]
    # Even share per page; pages shorter than their share give the rest to the others.
    sizes = {i: len(b) for i, b in enumerate(blocks)}
    remaining, open_ = budget, set(sizes)
    alloc = {}
    while open_:
        share = remaining // len(open_)
        small = {i for i in open_ if sizes[i] <= share}
        if not small:
            for i in open_:
                alloc[i] = share
            break
        for i in small:
            alloc[i] = sizes[i]
            remaining -= sizes[i]
        open_ -= small
    out = head + "".join(_cut(b, alloc[i]) for i, b in enumerate(blocks)) + tail
    return out[:limit] if len(out) > limit else out
