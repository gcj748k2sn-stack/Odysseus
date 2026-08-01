"""`/api/documents/ai-tidy` must say why it failed — docs/todo.md item 44.

Five recorded calls, five failures (4x `500` on 2026-07-30 17:31/17:32 and
2026-08-01 10:12/10:14, plus one `504`), and **not one of them wrote an ERROR
or a traceback**. The only trace of any was `app.slow_request`, the middleware
warning that exists to flag slow requests, not failed ones — which is why the
endpoint had been broken for at least three days without anyone noticing.

The mechanism was a bare re-raise: the route raises `HTTPException(500, "AI
returned invalid response")` when the model's reply contains no `[...]`, and
`except HTTPException: raise` sent it out of the building unlogged.

⚠️ **This is report-only.** Nothing here changes what the route *does* —
the same inputs still produce the same status codes and the same body. Only
the record changes. The cause of the 500 (a thinking model spending a
200-token budget before it emits the array — qwensetup.md §3) is deliberately
NOT addressed: item 44's first step is to record what comes back, because
until that exists every hypothesis about it is unfalsifiable.

**Negative controls are the first two tests.** A checker with only positive
cases can be a function that always fires: a successful tidy must log no
failure line at all, and a well-formed reply must not trip the parse branch.
"""

import logging
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
from core.database import Document
from core.database import Session as DbSession

OWNER = "alice"
BODY = "A real document body, long enough that no junk heuristic applies to it."

_TMPDB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_ENGINE = create_engine(
    f"sqlite:///{_TMPDB.name}",
    connect_args={"check_same_thread": False},
    poolclass=NullPool,
)
cdb.Base.metadata.create_all(_ENGINE)
_TS = sessionmaker(bind=_ENGINE, autoflush=False, autocommit=False)


def _req(user=OWNER):
    return SimpleNamespace(state=SimpleNamespace(current_user=user))


def _endpoint(method, path):
    router = droutes.setup_document_routes(MagicMock(), None)
    for route in router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise RuntimeError(f"{method} {path} not found")


@pytest.fixture
def ai_tidy(monkeypatch):
    """Bind the route to a scratch database and a stub endpoint resolver.

    The resolver is stubbed rather than the settings file so the test does not
    depend on `data/settings.json`, whose `task_model` is empty on this machine
    and which the running app rewrites wholesale on every save.
    """
    monkeypatch.setattr(droutes, "SessionLocal", _TS)
    # Wipe between tests. Without this the unreviewed backlog carries over and
    # a later test's `batch` silently contains an earlier test's fixtures —
    # every assertion here would still pass while measuring the wrong rows.
    _wipe = _TS()
    _wipe.query(Document).delete()
    _wipe.query(DbSession).delete()
    _wipe.commit()
    _wipe.close()
    import src.task_endpoint as te
    import src.endpoint_resolver as er
    monkeypatch.setattr(
        te, "resolve_task_endpoint",
        lambda *a, **k: ("http://localhost:11434/v1/chat/completions", "stub-model:4b", {}),
    )
    monkeypatch.setattr(er, "resolve_endpoint", lambda *a, **k: ("http://x", "stub-model:4b", {}))
    return _endpoint("POST", "/api/documents/ai-tidy")


def _seed(n=2):
    """Unreviewed, unarchived documents — the only kind ai-tidy looks at."""
    db = _TS()
    sid = str(uuid.uuid4())
    db.add(DbSession(id=sid, name=sid, endpoint_url="http://x", model="m", owner=OWNER))
    db.flush()
    ids = []
    for i in range(n):
        doc = Document(
            id=str(uuid.uuid4()), title=f"doc {i}", current_content=BODY,
            session_id=sid, owner=OWNER, is_active=True, archived=False,
        )
        db.add(doc)
        ids.append(doc.id)
    db.commit()
    db.close()
    return ids


def _stub_llm(monkeypatch, reply):
    async def _call(*a, **k):
        return reply
    import src.llm_core as llm
    monkeypatch.setattr(llm, "llm_call_async", _call)


def _records(caplog, marker="[ai-tidy]"):
    return [r for r in caplog.records if marker in r.getMessage()]


# --------------------------------------------------------------------------
# Negative controls — these must produce NO failure record.
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_successful_tidy_logs_no_failure(ai_tidy, monkeypatch, caplog):
    """A well-formed reply must not trip either failure branch.

    Without this, a bug that logged the error unconditionally would pass every
    positive test in this file.
    """
    _seed(2)
    _stub_llm(monkeypatch, '["keep","keep"]')
    with caplog.at_level(logging.INFO):
        result = await ai_tidy(_req())

    assert result["reviewed"] == 2
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING and "[ai-tidy]" in r.getMessage()]


@pytest.mark.asyncio
async def test_nothing_to_review_logs_no_failure(ai_tidy, monkeypatch, caplog):
    """The early return path must stay silent — it is a success, not a failure."""
    _stub_llm(monkeypatch, "never called")
    with caplog.at_level(logging.INFO):
        result = await ai_tidy(_req(user="nobody-with-no-docs"))

    assert result["reviewed"] == 0
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING and "[ai-tidy]" in r.getMessage()]


# --------------------------------------------------------------------------
# The recorded failure: a reply with no JSON array at all.
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reply_without_array_is_logged_before_the_500(ai_tidy, monkeypatch, caplog):
    """This is the branch every recorded ai-tidy 500 reached.

    A thinking model that spends its 200-token budget reasoning emits prose and
    no array. Before item 44 this raised silently.
    """
    _seed(2)
    _stub_llm(monkeypatch, "Okay, let me think about which of these documents are junk")
    with caplog.at_level(logging.INFO):
        with pytest.raises(HTTPException) as exc:
            await ai_tidy(_req())

    assert exc.value.status_code == 500
    errors = [r for r in _records(caplog) if r.levelno >= logging.ERROR]
    assert errors, "the 500 must not be raised without a logged reason"
    msg = errors[0].getMessage()
    assert "no JSON array" in msg
    assert "stub-model:4b" in msg, "the model must be named — it is not derivable from app.log otherwise"


@pytest.mark.asyncio
async def test_empty_reply_is_logged_with_its_length(ai_tidy, monkeypatch, caplog):
    """An empty reply and a chatty one fail identically to the caller.

    `chars=` is what separates "the model said nothing" from "the model said
    the wrong thing", which is the first question anyone will ask.
    """
    _seed(1)
    _stub_llm(monkeypatch, "")
    with caplog.at_level(logging.INFO):
        with pytest.raises(HTTPException):
            await ai_tidy(_req())

    errors = [r for r in _records(caplog) if r.levelno >= logging.ERROR]
    assert errors and "chars=0" in errors[0].getMessage()


# --------------------------------------------------------------------------
# The second failure mode, kept distinct from the first on purpose.
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_malformed_array_is_logged_distinctly(ai_tidy, monkeypatch, caplog):
    """Brackets present but unparseable is a DIFFERENT fault from no brackets.

    Conflating them is how "the tidy is broken" stays one undiagnosable bug
    instead of two findable ones.
    """
    _seed(1)
    _stub_llm(monkeypatch, '["junk", ,]')
    with caplog.at_level(logging.INFO):
        with pytest.raises(Exception):
            await ai_tidy(_req())

    msgs = [r.getMessage() for r in _records(caplog) if r.levelno >= logging.ERROR]
    assert any("did not parse" in m for m in msgs)
    assert not any("no JSON array" in m for m in msgs), "the two branches must not both fire"


# --------------------------------------------------------------------------
# The bare re-raise that made all of this invisible.
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_every_http_exit_names_itself(ai_tidy, monkeypatch, caplog):
    """`except HTTPException: raise` is why five failures wrote nothing.

    Mutation that kills this: delete the `logger.warning` from that handler and
    re-run — the ERROR above still fires, so only this test fails. That is the
    point of keeping it separate.
    """
    _seed(1)
    _stub_llm(monkeypatch, "no array here")
    with caplog.at_level(logging.INFO):
        with pytest.raises(HTTPException):
            await ai_tidy(_req())

    warnings = [r for r in _records(caplog) if r.levelno == logging.WARNING]
    assert warnings, "the HTTPException re-raise must record the status it returns"
    assert "500" in warnings[0].getMessage()


@pytest.mark.asyncio
async def test_start_line_names_the_model(ai_tidy, monkeypatch, caplog):
    """Which model ai-tidy runs on was previously only derivable from source.

    `resolve_task_endpoint` -> `resolve_endpoint("task")` with an empty
    `task_model` falls through a chain that no log line recorded, so a run
    could not be correlated with `ollama ps`.
    """
    _seed(1)
    _stub_llm(monkeypatch, '["keep"]')
    with caplog.at_level(logging.INFO):
        await ai_tidy(_req())

    starts = [r.getMessage() for r in _records(caplog) if "start" in r.getMessage()]
    assert starts and "stub-model:4b" in starts[0]
