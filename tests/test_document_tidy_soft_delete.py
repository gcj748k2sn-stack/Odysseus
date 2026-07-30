"""The document tidy must never destroy a row — docs/todo.md item 32.

On 2026-07-30 the duplicate pass hard-deleted 8 documents in a single run
(`task_runs.ad505282`: *"Removed 8 of 70 … (+8 duplicate copies) · 62 kept"*).
All 8 came from ONE group of nine byte-identical clones — the injected input to
item 20's five-run experiment, one clone per chat. `DocumentVersion` is
`cascade="all, delete-orphan"` with `ondelete="CASCADE"`, so every version row
went with them, and `app.log` recorded only *"Task 'Documents Tidy' completed"*.

Two properties are pinned here:

1. **Nothing is deleted.** Junk and duplicates are archived (`archived=True`,
   `is_active=False`), so the row and its versions survive and the user can
   restore from the Archive tab.
2. **The duplicate pass does not reach across chats.** The same document cloned
   into five chats is five working copies, not five duplicates. Two copies in
   the SAME chat are still duplicates and are still collapsed.

The first two tests are negative controls: a tidy with nothing to do must do
nothing, and a real document must survive a run that archives its neighbours.
A checker with only positive cases can be a function that always fires.
"""
import asyncio
import tempfile
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

import core.database as cdb
from core.database import Document, DocumentVersion

OWNER = "alice"
BODY = "A real document body, long enough that no junk rule applies to it here."
# Older than the 15-minute freshness skip in run_document_tidy.
OLD = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=3)


@pytest.fixture
def db_factory(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    engine = create_engine(f"sqlite:///{tmp.name}", connect_args={"check_same_thread": False}, poolclass=NullPool)
    cdb.Base.metadata.create_all(engine)
    TS = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(cdb, "SessionLocal", TS)
    return TS


def _chat(db, sid):
    """`documents.session_id` is a real FK — a document cannot name a chat that
    does not exist, so the cross-chat test needs actual Session rows."""
    if db.query(cdb.Session).filter(cdb.Session.id == sid).one_or_none() is None:
        db.add(cdb.Session(id=sid, name=sid, endpoint_url="http://x", model="m", owner=OWNER))
        db.flush()


def _doc(db, *, title=BODY[:20], content=BODY, session_id=None, versions=0):
    if session_id:
        _chat(db, session_id)
    d = Document(id=str(uuid.uuid4()), owner=OWNER, title=title, current_content=content,
                 session_id=session_id, is_active=True, archived=False,
                 created_at=OLD, updated_at=OLD)
    db.add(d)
    for n in range(versions):
        db.add(DocumentVersion(id=str(uuid.uuid4()), document_id=d.id,
                               version_number=n + 1, content=content, source="ai"))
    return d


async def _tidy():
    from src.document_actions import run_document_tidy
    return await run_document_tidy(OWNER)


def _run():
    """Return the result string, or None when the action reported nothing to do."""
    from src.builtin_actions import TaskNoop
    try:
        return asyncio.run(_tidy())
    except TaskNoop:
        return None


def _rows(db_factory):
    db = db_factory()
    try:
        return {d.id: (d.archived, d.is_active) for d in db.query(Document).all()}
    finally:
        db.close()


# --- negative controls -------------------------------------------------------

def test_a_library_of_distinct_documents_is_left_alone(db_factory):
    """Nothing to do must mean nothing done — including no archiving."""
    db = db_factory()
    try:
        for i in range(4):
            _doc(db, title=f"Report {i}", content=f"{BODY} number {i}")
        db.commit()
    finally:
        db.close()

    assert _run() is None, "a clean library must report a no-op, not a removal"
    assert all(a is False and act is True for a, act in _rows(db_factory).values())


def test_a_real_document_survives_a_run_that_archives_its_neighbour(db_factory):
    db = db_factory()
    try:
        keep = _doc(db, title="Quarterly report", content=BODY)
        _doc(db, title="asdf", content="asdf")  # junk title
        db.commit()
        keep_id = keep.id
    finally:
        db.close()

    assert _run() is not None
    rows = _rows(db_factory)
    assert rows[keep_id] == (False, True)


# --- nothing is destroyed ----------------------------------------------------

def test_junk_is_archived_not_deleted(db_factory):
    db = db_factory()
    try:
        junk = _doc(db, title="test", content="test", versions=2)
        db.commit()
        junk_id = junk.id
    finally:
        db.close()

    result = _run()
    assert result is not None and "Archived" in result

    db = db_factory()
    try:
        row = db.query(Document).filter(Document.id == junk_id).one_or_none()
        assert row is not None, "the row was DELETED — item 32's regression"
        assert (row.archived, row.is_active) == (True, False)
        # The cascade is why a delete here is unrecoverable; prove it didn't run.
        assert db.query(DocumentVersion).filter(DocumentVersion.document_id == junk_id).count() == 2
    finally:
        db.close()


def test_duplicates_in_one_chat_collapse_but_survive_as_rows(db_factory):
    db = db_factory()
    try:
        # Byte-identical, so they share a fingerprint and tie on real length —
        # the keeper is then the more recently updated one.
        a = _doc(db, title="Growth phases", content=BODY, session_id="chat-1", versions=1)
        b = _doc(db, title="Growth phases", content=BODY, session_id="chat-1", versions=1)
        b.updated_at = OLD + timedelta(minutes=30)
        db.commit()
        a_id, b_id = a.id, b.id
    finally:
        db.close()

    assert _run() is not None
    rows = _rows(db_factory)
    assert len(rows) == 2, "a duplicate row was deleted rather than archived"
    assert rows[b_id] == (False, True), "the newer copy should be the keeper"
    assert rows[a_id] == (True, False)

    db = db_factory()
    try:
        assert db.query(DocumentVersion).count() == 2
    finally:
        db.close()


# --- the pass does not reach across chats ------------------------------------

def test_the_same_document_cloned_into_five_chats_is_not_a_duplicate_group(db_factory):
    """The exact shape of the 2026-07-30 loss: nine identical clones, one per chat."""
    db = db_factory()
    try:
        for i in range(5):
            _doc(db, title="Pink Oyster Mushroom Growth Phases", content=BODY, session_id=f"chat-{i}")
        db.commit()
    finally:
        db.close()

    assert _run() is None, "clones in separate chats were treated as duplicates"
    rows = _rows(db_factory)
    assert len(rows) == 5
    assert all(r == (False, True) for r in rows.values())


def test_session_less_documents_still_group_together(db_factory):
    """`session_id IS NULL` is a real key, not an escape hatch.

    Documents whose chat was deleted all carry NULL, so they group with each
    other — that is the pre-existing behaviour and it is deliberate.
    """
    db = db_factory()
    try:
        _doc(db, title="Orphan", content=BODY, session_id=None)
        _doc(db, title="Orphan", content=BODY, session_id=None)
        db.commit()
    finally:
        db.close()

    assert _run() is not None
    rows = _rows(db_factory)
    assert len(rows) == 2
    assert sorted(rows.values()) == [(False, True), (True, False)]


# --- retiring is terminal ----------------------------------------------------

def test_a_second_run_does_not_re_report_what_the_first_archived(db_factory):
    """Archived rows are excluded from the query, so the action is idempotent.

    Without that filter the second run re-counts the same documents and the
    duplicate pass re-picks a keeper among rows the user was already told were
    removed.
    """
    db = db_factory()
    try:
        _doc(db, title="test", content="test")
        _doc(db, title="Real one", content=BODY)
        db.commit()
    finally:
        db.close()

    first = _run()
    assert first is not None and "Archived 1 of 2" in first
    assert _run() is None, "the second run saw the document it had already archived"
