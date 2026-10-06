"""A document named from another chat is used for the turn, not moved there
(docs/todo.md item 62, server half).

Seen 2026-10-05 23:31 and 23:38: `routes/chat_routes.py` logged "cross-session
active_doc_id … accepting and rebinding" and set the document's session_id to
the sending chat — the "Pink Oyster" document moved twice in 8 minutes, and its
updated_at changed although its content did not. 11 such moves in app.log since
2026-07-14. The browser half (82892264) stops the stale id being sent after New
Chat; this half stops the server moving a document whatever sends the id.

Runs `_explicit_active_document` against a real SQLite database (in memory,
foreign keys on, like the app).
"""
import logging
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import routes.chat_routes as cr
from core.database import Base, Document, Session as DBSession

STAMP = datetime(2026, 7, 30, 15, 11, 26)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    for sid in ("chat-a", "chat-b"):
        s.add(DBSession(id=sid, name=sid, endpoint_url="http://localhost:8090/v1", model="bonsai2-27b"))
    s.add(Document(id="doc-1", session_id="chat-a", title="Pink Oyster", language="markdown",
                   current_content="# Pink Oyster\n", owner="cedrik", is_active=True,
                   created_at=STAMP, updated_at=STAMP))
    s.add(Document(id="doc-other", session_id="chat-a", title="Not yours", language="markdown",
                   current_content="x", owner="mallory", is_active=True,
                   created_at=STAMP, updated_at=STAMP))
    s.commit()
    yield Session
    s.close()
    engine.dispose()


def _fresh(Session, doc_id):
    s = Session()
    try:
        d = s.query(Document).filter(Document.id == doc_id).one()
        return d.session_id, d.updated_at
    finally:
        s.close()


def test_cross_chat_document_is_used_but_not_moved(db, caplog):
    caplog.set_level(logging.INFO, logger=cr.logger.name)
    s = db()
    doc = cr._explicit_active_document(s, "doc-1", "chat-b", "cedrik")
    assert doc is not None and doc.title == "Pink Oyster"  # still used for this turn
    assert not s.dirty, "the helper must not leave a pending change on the document"
    s.commit()  # anything the helper left pending would land now
    s.close()

    session_id, updated_at = _fresh(db, "doc-1")
    assert session_id == "chat-a"
    assert updated_at == STAMP
    msgs = [r.getMessage() for r in caplog.records]
    assert any("cross-session active_doc_id doc-1" in m and "not moved" in m for m in msgs)


def test_same_chat_document_is_returned_unchanged(db, caplog):
    """Negative control: the ordinary case — no mismatch, no cross-session log."""
    caplog.set_level(logging.INFO, logger=cr.logger.name)
    s = db()
    doc = cr._explicit_active_document(s, "doc-1", "chat-a", "cedrik")
    s.commit()
    s.close()
    assert doc is not None
    assert _fresh(db, "doc-1") == ("chat-a", STAMP)
    assert not any("cross-session" in r.getMessage() for r in caplog.records)


def test_another_users_document_is_refused(db):
    s = db()
    assert cr._explicit_active_document(s, "doc-other", "chat-b", "cedrik") is None
    s.close()
    assert _fresh(db, "doc-other") == ("chat-a", STAMP)


def test_unknown_id_is_none(db):
    s = db()
    assert cr._explicit_active_document(s, "no-such-doc", "chat-b", "cedrik") is None
    s.close()
