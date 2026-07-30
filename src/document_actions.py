"""
document_actions.py

Reusable document actions callable from both REST routes and the task scheduler.
"""

import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


_JUNK_TITLES = {
    "untitled", "untitled document", "new document", "document",
    "new email", "new mail", "new message", "reply", "fwd", "re:",
    "test", "testing", "asdf", "asd", "foo", "bar", "baz",
    "tmp", "temp", "scratch", "scratchpad", "draft", "delete",
    "remove", "junk", "trash", "xxx", "abc", "qwerty",
}


def _norm_title(t: str) -> str:
    """Normalize a title for grouping: trim, collapse whitespace, lowercase."""
    t = t if isinstance(t, str) else ""
    return re.sub(r"\s+", " ", t.strip()).lower()


def _content_fingerprint(content: str) -> str:
    """A stable fingerprint of document content for duplicate detection.

    Strips bits that differ between otherwise-identical copies — chiefly the
    `upload_id` of a re-imported PDF and the random `id=` of annotations — so
    that N imports of the same file collapse to one fingerprint. Whitespace is
    collapsed and the result lowercased.
    """
    c = content if isinstance(content, str) else ""
    c = re.sub(r'upload_id="[^"]*"', "upload_id", c)          # pdf_source re-imports
    c = re.sub(r"\bid=ann-[A-Za-z0-9_-]+", "id=ann", c)        # annotation ids
    c = re.sub(r"\s+", " ", c).strip().lower()
    return c


def retire_document(doc, reason: str, retired: list) -> None:
    """Soft-remove a document: archive it and drop it from the tab bar.

    **This function exists so that no tidy path calls `db.delete` on a
    Document.** docs/todo.md item 32. On 2026-07-30 the duplicate pass
    hard-deleted 8 documents in one run (`task_runs.ad505282`, *"Removed 8 of
    70 … (+8 duplicate copies) · 62 kept"*) — a single group of nine
    byte-identical clones, which were the *input* to item 20's experiment.
    `DocumentVersion` is `cascade="all, delete-orphan"` with
    `ondelete="CASCADE"`, so the entire version history went with each row and
    nothing was recoverable.

    `archived = True` puts it in the library's Archive tab, where the user can
    restore it, and every tidy query filters archived rows out — so a second
    run does not re-count what a first one retired. `is_active = False` removes
    it from the chat's tab bar, which is the visible behaviour the tidy is
    *for*; without it, "tidy" would leave the clutter on screen.

    ⚠️ Callers must record the ids: `task_runs.result` holds a 40-character
    title preview and nothing else, which is why the 07-30 deletions had to be
    reconstructed from a result string rather than read from a log.
    """
    doc.archived = True
    doc.is_active = False
    retired.append((doc.id, reason))


def _real_len(content: str) -> int:
    """Length of content with markdown noise stripped — a 'completeness' proxy."""
    content = content if isinstance(content, str) else ""
    stripped = re.sub(r"^#{1,6}\s+", "", content, flags=re.MULTILINE)
    stripped = re.sub(r"[*_`>\-=]+", "", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    return len(stripped)


async def run_document_tidy(owner: str) -> str:
    """Remove clearly-junk documents and redundant duplicates for an owner.

    Conservative rules (no length-based deletion — short notes are valid):
    - Empty / whitespace-only / placeholder ("# Untitled")
    - Title is a throwaway name (test, asdf, …) or the content itself is one
    - Email reply-chain with no original content
    - Duplicates: docs sharing the same normalized title AND the same content
      fingerprint (ignoring volatile upload/annotation ids). The most complete
      copy (longest real content, then most recent) is kept; the rest deleted.
    """
    from core.database import SessionLocal, Document, Session as DbSession

    db = SessionLocal()
    try:
        # Already-archived documents are invisible to this pass. Retiring is
        # idempotent only if a second run cannot see what the first one
        # retired — otherwise every run re-counts the same rows and the
        # duplicate pass re-picks a keeper among documents the user has
        # already been told were removed. `None` is a legacy row that predates
        # the column, i.e. not archived. docs/todo.md item 32.
        from sqlalchemy import or_ as _or
        _live = _or(Document.archived == False, Document.archived.is_(None))  # noqa: E712
        if owner:
            # Documents now carry their own owner column (robust to a deleted
            # session). Match on it directly; orphaned legacy rows are swept
            # to the admin at boot so they're attributed too.
            docs = db.query(Document).filter(Document.owner == owner).filter(_live).all()
        else:
            docs = db.query(Document).filter(_live).all()

        retired: list = []
        deleted_examples = []
        deleted = 0
        kept = 0
        survivors = []  # docs that pass the junk rules, considered for dedup
        now = datetime.now(timezone.utc)

        for doc in docs:
            created = doc.created_at
            if created and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)

            # Skip freshly created documents to avoid deleting them while the user is actively editing
            if created and (now - created).total_seconds() < 900:  # 15 minutes
                survivors.append(doc)
                continue

            content = (doc.current_content or "").strip()
            title = (doc.title or "").strip().lower()
            is_fresh_empty = (
                not content
                and created is not None
                and (now - created).total_seconds() < 1800
            )
            if is_fresh_empty:
                survivors.append(doc)
                continue

            # Strip markdown noise to get "real" character count
            stripped = re.sub(r"^#{1,6}\s+", "", content, flags=re.MULTILINE)  # headers
            stripped = re.sub(r"[*_`>\-=]+", "", stripped)  # markdown chars
            stripped = re.sub(r"\s+", " ", stripped).strip()
            real_len = len(stripped)

            # Detect emails-saved-as-documents (quote chains with no original content)
            lines = [ln for ln in content.split("\n") if ln.strip()]
            quoted_lines = [ln for ln in lines if ln.lstrip().startswith(">")]
            header_lines = [ln for ln in lines if re.match(r"^On .+ wrote:?\s*$", ln.strip())]
            non_quote_content = "\n".join(
                ln for ln in lines
                if not ln.lstrip().startswith(">")
                and not re.match(r"^On .+ wrote:?\s*$", ln.strip())
            ).strip()
            quote_ratio = len(quoted_lines) / max(len(lines), 1)

            should_delete = False
            reason = ""

            if not content or content in ("", "# Untitled"):
                should_delete = True
                reason = "empty"
            elif title in _JUNK_TITLES:
                # If you named it "test" or "asdf" etc, you don't care about it
                should_delete = True
                reason = f"junk title '{title}'"
            elif stripped.lower() in _JUNK_TITLES:
                should_delete = True
                reason = "throwaway content"
            # No length-based deletion: short notes are legitimate content.
            elif (quoted_lines or header_lines) and len(non_quote_content) < 50 and quote_ratio > 0.4:
                # Email reply chain with no original content
                should_delete = True
                reason = "email quote-chain only"

            if should_delete:
                if len(deleted_examples) < 5:
                    label = (doc.title or "(no title)")[:40]
                    deleted_examples.append(f"{label} ({reason})")
                retire_document(doc, reason, retired)
                deleted += 1
            else:
                survivors.append(doc)

        # --- Duplicate pass: group survivors by (normalized title, content
        # fingerprint, SESSION) and keep only the most complete copy of each
        # group. ---
        #
        # ⚠️ `session_id` is part of the key, and that is the point. Without it
        # the pass reaches across chats, and "the same document cloned into
        # five chats" is exactly what a duplicate looks like — same title, same
        # bytes, different owner-session. That is not redundancy; it is five
        # separate working copies, and collapsing them is what destroyed item
        # 20's nine clones on 2026-07-30. Two copies in the SAME chat are still
        # duplicates and are still collapsed. docs/todo.md item 32.
        groups: dict = {}
        for doc in survivors:
            key = (_norm_title(doc.title), _content_fingerprint(doc.current_content), doc.session_id)
            groups.setdefault(key, []).append(doc)

        for (title_key, _fp, _sess), members in groups.items():
            if len(members) < 2:
                kept += 1
                continue
            # Keep the most complete (longest real content), then most recent.
            def _updated(d):
                return d.updated_at or d.created_at
            # Sort key must be total-order safe: a document with both
            # updated_at and created_at NULL would otherwise make Python
            # compare None against a datetime on a real-length tie, raising
            # TypeError and aborting the whole tidy run. Rank "has a
            # timestamp" before the timestamp itself so a None is never
            # compared against a datetime.
            members.sort(
                key=lambda d: (
                    _real_len(d.current_content),
                    _updated(d) is not None,
                    _updated(d) or datetime.min,
                ),
                reverse=True,
            )
            keeper = members[0]
            kept += 1
            dupes = members[1:]
            if len(deleted_examples) < 5:
                label = (keeper.title or "(no title)")[:40]
                deleted_examples.append(f"{label} (+{len(dupes)} duplicate copies)")
            for d in dupes:
                retire_document(d, f"duplicate of {keeper.id}", retired)
                deleted += 1

        if deleted:
            db.commit()
            # The ids, in the log, at the moment it happens. `task_runs.result`
            # keeps a truncated title preview; that is not enough to answer
            # "which document did this take" after the fact. docs/todo.md 32.
            logger.info(
                "[doc-tidy] archived %d document(s) for owner=%r: %s",
                len(retired), owner, "; ".join(f"{i} ({r})" for i, r in retired),
            )

        if deleted == 0:
            # Use sentinel so the scheduler can drop the run row entirely.
            from src.builtin_actions import TaskNoop
            raise TaskNoop(f"scanned {len(docs)} document(s), no junk")
        preview = "; ".join(deleted_examples)
        extra = f" (+{deleted - len(deleted_examples)} more)" if deleted > len(deleted_examples) else ""
        # "Archived", not "Removed" — the word in this string is the only
        # account most people will ever read of what happened.
        return f"Archived {deleted} of {len(docs)}: {preview}{extra} · {kept} kept · restore from the Archive tab"
    finally:
        db.close()
