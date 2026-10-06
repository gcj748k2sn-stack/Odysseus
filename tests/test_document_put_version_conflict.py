"""Lost-update guard on PUT /api/document/{doc_id}.

Context: notes/resolvedissues.md, "Autosave reverting AI edits" — fixed and
verified live 2026-07-19. Note the final diagnosis differs from the one below:
the root cause was a duplicated doc_update SSE event, not autosave and not this
compare-and-swap, both of which behaved correctly throughout. This guard is
still correct and still load-bearing; it just was not the bug.

The browser autosave used to PUT a stale cached copy back over a newer
AI-written version ~60ms after the AI edit landed, recorded as source="user"
(observed 2026-07-18: v3 user == v1 content). The fix: the client sends the
version_count its content is based on (`base_version`); the server rejects
with 409 when the document has moved past it.

Pinned directions:
  1. base_version == current version_count -> save succeeds, version bumps.
  2. base_version <  current version_count (stale cache) -> 409, content and
     version history untouched.
  3. base_version omitted (legacy/other callers) -> old behaviour, saves.
  4. identical content + stale base_version -> no-op success (harmless echo
     must not turn into a scary 409).

Route handlers are called directly (same pattern as
test_auth_disabled_document_access.py).
"""

import tempfile
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from tests.helpers.import_state import clear_fake_database_modules

clear_fake_database_modules()

import core.database as cdb
import routes.document_routes as droutes
from core.database import Document, DocumentVersion
from core.database import Session as DbSession
from routes.document_helpers import DocumentUpdate

_TMPDB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_ENGINE = create_engine(
    f"sqlite:///{_TMPDB.name}",
    connect_args={"check_same_thread": False},
    poolclass=NullPool,
)
cdb.Base.metadata.create_all(_ENGINE)
_TS = sessionmaker(bind=_ENGINE, autoflush=False, autocommit=False)


def _req(user=None):
    return SimpleNamespace(state=SimpleNamespace(current_user=user))


def _endpoint(method, path):
    router = droutes.setup_document_routes(MagicMock(), None)
    for route in router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise RuntimeError(f"{method} {path} not found")


def _seed(content="v1 body", version_count=1, owner="alice"):
    session_id = f"{owner}-" + uuid.uuid4().hex[:8]
    doc_id = str(uuid.uuid4())
    db = _TS()
    try:
        db.add(DbSession(
            id=session_id, owner=owner, name=owner,
            model="m", endpoint_url="http://x",
        ))
        db.add(Document(
            id=doc_id,
            session_id=session_id,
            title="doc",
            language="markdown",
            current_content=content,
            version_count=version_count,
            is_active=True,
            owner=owner,
        ))
        db.commit()
        return doc_id
    finally:
        db.close()


def _doc_state(doc_id):
    db = _TS()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        vers = db.query(DocumentVersion).filter(
            DocumentVersion.document_id == doc_id
        ).count()
        return doc.current_content, doc.version_count, vers
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _auth_off_and_test_db(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    previous = droutes.SessionLocal
    droutes.SessionLocal = _TS
    yield
    droutes.SessionLocal = previous


@pytest.mark.asyncio
async def test_matching_base_version_saves():
    put = _endpoint("PUT", "/api/document/{doc_id}")
    doc_id = _seed(content="v1 body", version_count=1)

    result = await put(_req(None), doc_id, DocumentUpdate(content="user edit", base_version=1))

    assert result["current_content"] == "user edit"
    assert result["version_count"] == 2


@pytest.mark.asyncio
async def test_stale_base_version_rejected_409():
    """The revert scenario: server is at v2 (AI edit), client PUTs v1-based content."""
    put = _endpoint("PUT", "/api/document/{doc_id}")
    doc_id = _seed(content="v2 ai content", version_count=2)

    with pytest.raises(HTTPException) as exc:
        await put(_req(None), doc_id, DocumentUpdate(content="stale v1 content", base_version=1))

    assert exc.value.status_code == 409
    detail = exc.value.detail
    assert detail["error"] == "version_conflict"
    assert detail["current_version"] == 2
    # Nothing was written: AI content and version history intact.
    content, version_count, n_versions = _doc_state(doc_id)
    assert content == "v2 ai content"
    assert version_count == 2
    assert n_versions == 0


@pytest.mark.asyncio
async def test_no_base_version_keeps_legacy_behaviour():
    put = _endpoint("PUT", "/api/document/{doc_id}")
    doc_id = _seed(content="v2 ai content", version_count=2)

    result = await put(_req(None), doc_id, DocumentUpdate(content="legacy save"))

    assert result["current_content"] == "legacy save"
    assert result["version_count"] == 3


@pytest.mark.asyncio
async def test_identical_content_with_stale_base_version_is_noop():
    put = _endpoint("PUT", "/api/document/{doc_id}")
    doc_id = _seed(content="same body", version_count=2)

    result = await put(_req(None), doc_id, DocumentUpdate(content="same body", base_version=1))

    assert result["current_content"] == "same body"
    assert result["version_count"] == 2


# --- Compare-and-swap: the base_version check alone is not enough ------------
#
# The early check compares against a value SELECTed at the top of the handler.
# An AI edit committing between that read and our write slips straight through
# — observed live 2026-07-18 07:49:02, where v5 clobbered v4 back to v2's
# content within the same second despite the guard being in place. These pin
# the atomic UPDATE ... WHERE version_count = :base_version that closes it.


@pytest.mark.asyncio
async def test_concurrent_ai_edit_after_read_loses_the_swap(monkeypatch):
    """Simulate the real race: the AI bumps version_count *after* the handler
    has read the document but *before* it writes."""
    put = _endpoint("PUT", "/api/document/{doc_id}")
    doc_id = _seed(content="v3 body", version_count=3)

    # Patch `reserve_upload_references`, NOT `_reserve_document_uploads`.
    # The latter is a closure nested in setup_document_routes() and never a
    # module attribute, so the old patch raised AttributeError on this line and
    # these two tests had never once run (notes/todo.md item 18). The closure's
    # whole body is a call to reserve_upload_references, imported at
    # routes/document_routes.py:15 and invoked unconditionally, so patching it
    # lands in the identical window: after `base_version = doc.version_count`,
    # before `db.add(ver)` and the compare-and-swap.
    original = droutes.reserve_upload_references
    fired = {"done": False}

    def _interleave(*args, **kwargs):
        # Runs after the base_version check, before the write — exactly the
        # window the old code left open.
        if not fired["done"]:
            fired["done"] = True
            db = _TS()
            try:
                d = db.query(Document).filter(Document.id == doc_id).first()
                d.current_content = "v4 ai correction"
                d.version_count = 4
                db.commit()
            finally:
                db.close()
        return original(*args, **kwargs)

    monkeypatch.setattr(droutes, "reserve_upload_references", _interleave)

    with pytest.raises(HTTPException) as exc:
        await put(_req(None), doc_id, DocumentUpdate(content="stale v3 content", base_version=3))

    assert exc.value.status_code == 409
    assert exc.value.detail["error"] == "version_conflict"
    assert exc.value.detail["current_version"] == 4

    # The AI's correction survived and the losing write left no version row.
    content, version_count, n_versions = _doc_state(doc_id)
    assert content == "v4 ai correction"
    assert version_count == 4
    assert n_versions == 0


@pytest.mark.asyncio
async def test_losing_swap_does_not_leave_a_partial_version_row(monkeypatch):
    """The DocumentVersion insert is staged before the swap; a lost swap must
    roll it back rather than leaving an orphan row in the history."""
    put = _endpoint("PUT", "/api/document/{doc_id}")
    doc_id = _seed(content="body", version_count=1)

    # See the note in the test above — same reason, same window.
    original = droutes.reserve_upload_references
    fired = {"done": False}

    def _interleave(*args, **kwargs):
        # Guarded rather than self-restoring: the old body reassigned
        # droutes._reserve_document_uploads to undo itself, which was a second
        # route to the same missing attribute. monkeypatch already restores.
        if not fired["done"]:
            fired["done"] = True
            db = _TS()
            try:
                d = db.query(Document).filter(Document.id == doc_id).first()
                d.version_count = 9
                db.commit()
            finally:
                db.close()
        return original(*args, **kwargs)

    monkeypatch.setattr(droutes, "reserve_upload_references", _interleave)

    with pytest.raises(HTTPException) as exc:
        await put(_req(None), doc_id, DocumentUpdate(content="new body", base_version=1))

    assert exc.value.status_code == 409
    _, _, n_versions = _doc_state(doc_id)
    assert n_versions == 0


@pytest.mark.asyncio
async def test_uncontended_write_still_succeeds():
    """The swap must not make the normal path stricter."""
    put = _endpoint("PUT", "/api/document/{doc_id}")
    doc_id = _seed(content="v1 body", version_count=1)

    result = await put(_req(None), doc_id, DocumentUpdate(content="clean edit", base_version=1))

    assert result["current_content"] == "clean edit"
    assert result["version_count"] == 2
    content, version_count, n_versions = _doc_state(doc_id)
    assert content == "clean edit"
    assert version_count == 2
    assert n_versions == 1
