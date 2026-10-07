"""Which of the user's own content may enter a prompt without arming the tool gate.

Upstream wraps every injected block (memories, the open document, web results,
email, …) with ``untrusted_context_message``, and any such block makes later
write tools in the run ask for approval. That treats a memory the user typed and
a document the user wrote like a web page, so ordinary document work raised
approval cards depending on whether a saved memory happened to be recalled
(notes: "Why the approval card appears only sometimes").

This module decides, fail-closed, when a block is the user's own:

- **Memory:** every entry has ``source == "user"`` (typed, or an AI suggestion
  the user confirmed). ``ai_agent`` / ``auto`` / tidied entries stay untrusted;
  AI paths that rewrite a memory's text relabel it.
- **Document:** not email-derived, and every version in its history is either a
  user edit after v1, an empty v1 (a blank new document), or an AI write this
  module recorded as made in a clean run. A non-empty v1 from the browser is an
  import, a copy or an opened file, and is trusted only when its text is
  identical to a version of another document that is itself trusted (opening a
  document from the Library copies it into the chat); ``upload``/``ocr`` versions are files from
  elsewhere; AI writes without a record (other loops, older history, a run that
  had seen untrusted context or ran under an approval) all count as untrusted.

The block is still wrapped as untrusted *data* for the model; only the gate
arming changes.
"""
import logging
from typing import Any, Iterable

logger = logging.getLogger(__name__)

# Fork-owned table, created on first use. Raw SQL so that importing this module
# (from chat_processor, say) does not import core.database, which initialises
# the database at import time. Valid on SQLite and Postgres.
_CREATE = (
    "CREATE TABLE IF NOT EXISTS ai_document_writes ("
    " document_id VARCHAR NOT NULL,"
    " version_number INTEGER NOT NULL,"
    " clean BOOLEAN NOT NULL,"
    " created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
    " PRIMARY KEY (document_id, version_number))"
)
_UPSERT = (
    "INSERT INTO ai_document_writes (document_id, version_number, clean)"
    " VALUES (:d, :v, :c)"
    " ON CONFLICT (document_id, version_number) DO UPDATE SET clean = excluded.clean"
)
_table_ready = False


def _session():
    global _table_ready
    from sqlalchemy import text
    from core.database import SessionLocal

    db = SessionLocal()
    if not _table_ready:
        db.execute(text(_CREATE))
        db.commit()
        _table_ready = True
    return db, text


def memories_are_user_authored(entries: Iterable[Any]) -> bool:
    entries = list(entries or ())
    return bool(entries) and all(
        isinstance(m, dict) and m.get("source") == "user" for m in entries
    )


def record_ai_document_write(result: Any, *, clean: bool) -> None:
    """Remember one successful agent document write. Never raises."""
    if not isinstance(result, dict):
        return
    doc_id, version = result.get("doc_id"), result.get("version")
    if not doc_id or not isinstance(version, int) or isinstance(version, bool):
        return
    try:
        db, text = _session()
        try:
            db.execute(text(_UPSERT), {"d": str(doc_id), "v": version, "c": bool(clean)})
            db.commit()
        finally:
            db.close()
    except Exception as exc:  # an unrecorded write is simply untrusted later
        logger.warning("could not record AI document write %s v%s: %s", doc_id, version, exc)


_COPY_DEPTH = 3  # a copy of a copy of …; bounded so a cycle cannot loop


def document_is_user_trusted(document: Any) -> bool:
    """True only when every version of the document is the user's own (see module doc)."""
    doc_id = getattr(document, "id", None)
    if not doc_id:
        return False
    if (getattr(document, "language", "") or "").lower() == "email" or any(
        getattr(document, f, None)
        for f in ("source_email_uid", "source_email_message_id", "source_email_account_id")
    ):
        return False
    try:
        db, text = _session()
        try:
            return _trusted(db, text, str(doc_id), _COPY_DEPTH, {str(doc_id)})
        finally:
            db.close()
    except Exception as exc:
        logger.warning("document trust check failed for %s: %s", doc_id, exc)
        return False


def _trusted(db, text, doc_id: str, depth: int, seen: set) -> bool:
    row = db.execute(
        text("SELECT language, source_email_uid, source_email_message_id,"
             " source_email_account_id FROM documents WHERE id = :d"),
        {"d": doc_id},
    ).fetchone()
    if row is None or (row[0] or "").lower() == "email" or any(row[1:]):
        return False
    versions = db.execute(
        text("SELECT version_number, source, content FROM document_versions"
             " WHERE document_id = :d"),
        {"d": doc_id},
    ).fetchall()
    clean_ai = {
        r[0] for r in db.execute(
            text("SELECT version_number FROM ai_document_writes"
                 " WHERE document_id = :d AND clean"),
            {"d": doc_id},
        ).fetchall()
    }
    if not versions:
        return False
    for number, source, content in versions:
        if source == "user":
            if number == 1 and (content or "").strip():
                if not _is_copy_of_trusted(db, text, doc_id, content, depth, seen):
                    return False
        elif source == "ai":
            if number not in clean_ai:
                return False
        else:
            return False
    return True


def _is_copy_of_trusted(db, text, doc_id: str, content: str, depth: int, seen: set) -> bool:
    """Identical text to a trusted document cannot carry anything new."""
    if depth <= 0:
        return False
    for (other,) in db.execute(
        text("SELECT DISTINCT document_id FROM document_versions"
             " WHERE content = :c AND document_id != :d"),
        {"c": content, "d": doc_id},
    ).fetchall():
        if other in seen:
            continue
        seen.add(other)
        if _trusted(db, text, other, depth - 1, seen):
            return True
    return False
