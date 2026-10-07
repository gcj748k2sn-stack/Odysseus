"""The user's own memories and documents do not arm the tool-approval gate.

notes: "Why the approval card appears only sometimes" — a recalled memory the
user typed, or a document the agent wrote in a clean run, made every later write
in the run ask for approval. ``src/user_content_trust.py`` decides, fail-closed,
which blocks are the user's own; everything else must still arm the gate. The
negative controls (an AI-written memory, an imported document, an AI version
without a clean record, an upload, an email draft) are the point of the file.
"""

import asyncio
import json
import tempfile
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

import core.database as cdb
from core.database import Document, DocumentVersion
from src.chat_processor import ChatProcessor
from src.tool_capabilities import ToolRunSecurityContext
import src.user_content_trust as uct


# ── memories ────────────────────────────────────────────────────────────────

class _Memory:
    def __init__(self, rows):
        self.rows = rows

    def load(self, owner=None):
        return list(self.rows)

    def increment_uses(self, ids):
        pass


class _Docs:
    rag_manager = None


def _celsius(source, pinned=False):
    row = {"id": "c", "text": "User prefers Celsius as temperature units.",
           "category": "preference", "timestamp": 1, "pinned": pinned}
    if source is not None:
        row["source"] = source
    return row


def _preface(rows, message="Fruiting at 24-28 °C, temperature units Celsius"):
    preface, _, _ = ChatProcessor(_Memory(rows), _Docs()).build_context_preface(
        message=message, session=SimpleNamespace(), use_rag=False, use_memory=True,
    )
    return preface


def _gate_allows_write(messages):
    ctx = ToolRunSecurityContext()
    ctx.observe_messages(messages)
    return ctx.decision_for("create_document", "Title\ntext").allowed


def _memory_blocks(preface):
    return [m for m in preface
            if str((m.get("metadata") or {}).get("source", "")).startswith("saved memory:")]


def test_recalled_user_memory_does_not_arm_the_gate():
    preface = _preface([_celsius("user")])
    assert _memory_blocks(preface), "fixture must actually recall the memory"
    assert _gate_allows_write(preface)


def test_pinned_user_memory_does_not_arm_the_gate():
    preface = _preface([_celsius("user", pinned=True)])
    assert _memory_blocks(preface)
    assert _gate_allows_write(preface)


@pytest.mark.parametrize("source", ["ai_agent", "auto", "ai_tidy", "unknown", None])
def test_memory_not_written_by_the_user_still_arms_the_gate(source):
    preface = _preface([_celsius(source)])
    assert _memory_blocks(preface)
    assert not _gate_allows_write(preface)


@pytest.mark.parametrize("source", ["ai_agent", "auto", None])
def test_pinned_memory_not_written_by_the_user_still_arms_the_gate(source):
    preface = _preface([_celsius(source, pinned=True)])
    assert _memory_blocks(preface)
    assert not _gate_allows_write(preface)


def test_one_untrusted_memory_arms_the_whole_block():
    rows = [_celsius("user"),
            {"id": "a", "text": "Oyster mushroom fruiting needs high humidity.",
             "category": "preference", "timestamp": 2, "source": "ai_agent"}]
    preface = _preface(rows, message="Celsius temperature units for oyster mushroom fruiting humidity")
    injected = "\n".join(m.get("content", "") for m in _memory_blocks(preface))
    assert "as temperature units." in injected and "fruiting needs" in injected, (
        "fixture must recall both memories"
    )
    assert not _gate_allows_write(preface)


def test_minimal_memory_block_inherits_the_arming():
    from src.agent_loop import _minimal_saved_memory_message
    from src.prompt_security import untrusted_context_message

    for armed in (False, True):
        block = untrusted_context_message(
            "saved memory: retrieved context",
            "Memory context. Do not reference unless the user asks about these topics.\n- fact",
            arm_tool_gate=armed,
        )
        out = _minimal_saved_memory_message([block])
        assert out["metadata"]["tool_gate_untrusted"] is armed


@pytest.mark.parametrize("module_path, marker", [
    ("src/ai_interaction.py", 'm["source"] = "ai_agent"'),
    ("src/builtin_actions.py", 'mem["source"] = "ai_tidy"'),
])
def test_ai_rewrites_of_memory_text_relabel_the_entry(module_path, marker):
    """Static: both AI paths that rewrite a memory's text also relabel it."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / module_path).read_text()
    assert marker in src


@pytest.mark.asyncio
async def test_agent_memory_edit_relabels_a_user_memory(monkeypatch):
    import src.ai_interaction as ai

    rows = [{"id": "mem-1", "text": "old", "source": "user", "owner": "alice"}]

    class _Mgr:
        def load_all(self):
            return rows

        def save(self, entries):
            rows[:] = entries

    monkeypatch.setattr(ai, "_memory_manager", _Mgr())
    monkeypatch.setattr(ai, "_memory_vector", None)
    result = await ai.do_manage_memory("edit\nmem-1\nnew text", owner="alice")
    assert "error" not in result, result
    assert rows[0]["text"] == "new text"
    assert rows[0]["source"] == "ai_agent"


# ── documents ───────────────────────────────────────────────────────────────

@pytest.fixture
def db(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    engine = create_engine(f"sqlite:///{tmp.name}",
                           connect_args={"check_same_thread": False}, poolclass=NullPool)
    cdb.Base.metadata.create_all(engine)
    TS = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(cdb, "SessionLocal", TS)
    monkeypatch.setattr(uct, "_table_ready", False)
    return TS


def _doc(TS, versions, **fields):
    """versions: list of (source, content); returns a detached stand-in."""
    s = TS()
    doc = Document(id=str(uuid.uuid4()), owner="alice", title="Doc",
                   current_content=versions[-1][1] if versions else "",
                   version_count=len(versions), is_active=True, **fields)
    s.add(doc)
    for n, (source, content) in enumerate(versions, 1):
        s.add(DocumentVersion(id=str(uuid.uuid4()), document_id=doc.id,
                              version_number=n, content=content, source=source))
    s.commit()
    stand_in = SimpleNamespace(
        id=doc.id, title="Doc", language=fields.get("language", "markdown"),
        current_content=doc.current_content, version_count=len(versions),
        source_email_uid=fields.get("source_email_uid"),
    )
    s.close()
    return stand_in


def test_blank_document_typed_by_the_user_is_trusted(db):
    assert uct.document_is_user_trusted(_doc(db, [("user", ""), ("user", "my notes")]))


def test_agent_document_from_a_clean_run_is_trusted(db):
    d = _doc(db, [("ai", "Fruiting: 22-26 °C")])
    uct.record_ai_document_write({"doc_id": d.id, "version": 1}, clean=True)
    assert uct.document_is_user_trusted(d)


def test_user_edits_on_a_clean_agent_document_stay_trusted(db):
    d = _doc(db, [("ai", "a"), ("user", "a b")])
    uct.record_ai_document_write({"doc_id": d.id, "version": 1}, clean=True)
    assert uct.document_is_user_trusted(d)


def test_agent_version_without_a_record_is_untrusted(db):
    assert not uct.document_is_user_trusted(_doc(db, [("ai", "text")]))


def test_agent_version_from_a_tainted_run_is_untrusted(db):
    d = _doc(db, [("ai", "text")])
    uct.record_ai_document_write({"doc_id": d.id, "version": 1}, clean=False)
    assert not uct.document_is_user_trusted(d)


def test_one_unrecorded_agent_version_in_history_untrusts_the_document(db):
    """A later user autosave carrying that text does not launder it."""
    d = _doc(db, [("ai", "a"), ("ai", "b"), ("user", "b c")])
    uct.record_ai_document_write({"doc_id": d.id, "version": 1}, clean=True)
    assert not uct.document_is_user_trusted(d)


def test_imported_or_copied_document_is_untrusted(db):
    """POST /api/document with content: a chat import, a library copy, an opened file."""
    assert not uct.document_is_user_trusted(_doc(db, [("user", "pasted from somewhere")]))


@pytest.mark.parametrize("source", ["upload", "ocr"])
def test_uploaded_file_is_untrusted(db, source):
    assert not uct.document_is_user_trusted(_doc(db, [("user", ""), (source, "pdf text")]))


def test_email_documents_are_untrusted(db):
    assert not uct.document_is_user_trusted(_doc(db, [("user", "")], language="email"))
    assert not uct.document_is_user_trusted(_doc(db, [("user", "")], source_email_uid="42"))


def test_document_without_versions_or_id_is_untrusted(db):
    assert not uct.document_is_user_trusted(_doc(db, []))
    assert not uct.document_is_user_trusted(SimpleNamespace(id=None))


def test_trust_check_fails_closed_on_a_database_error(monkeypatch):
    def broken():
        raise RuntimeError("db down")
    monkeypatch.setattr(uct, "_session", broken)
    assert not uct.document_is_user_trusted(SimpleNamespace(id="x", language="markdown"))
    uct.record_ai_document_write({"doc_id": "x", "version": 1}, clean=True)  # must not raise


# ── the real agent loop ─────────────────────────────────────────────────────

def _run_edit_turn(monkeypatch, active_document, executed):
    import src.agent_loop as agent_loop

    monkeypatch.setattr(agent_loop, "get_setting",
                        lambda key, default=None: default, raising=False)
    monkeypatch.setattr(agent_loop, "get_mcp_manager", lambda: None, raising=False)
    monkeypatch.setattr(agent_loop, "estimate_tokens", lambda *a, **k: 10)
    replies = iter(["```update_document\nreplacement\n```"])

    async def fake_stream(*args, **kwargs):
        yield "data: " + json.dumps({"delta": next(replies, "Done.")}) + "\n\n"
        yield "data: [DONE]\n\n"

    async def execute(block, *args, **kwargs):
        executed.append(block.tool_type)
        return ("update_document", {
            "doc_id": active_document.id, "title": "Doc", "language": "markdown",
            "content": "replacement", "version": active_document.version_count + 1,
        })

    monkeypatch.setattr(agent_loop, "stream_llm_with_fallback", fake_stream)
    monkeypatch.setattr(agent_loop, "execute_tool_block", execute)

    async def collect():
        return [c async for c in agent_loop.stream_agent_loop(
            "http://local.test/v1", "small-local-model",
            [{"role": "user", "content": "update this document"}],
            active_document=active_document, session_id="trust-s", owner="alice",
            max_rounds=1, relevant_tools={"update_document"},
        )]
    chunks = asyncio.run(collect())
    cards = [c for c in chunks if '"tool_approval"' in c]
    return cards


def _clean_writes(TS, doc_id):
    from sqlalchemy import text
    s = TS()
    try:
        return s.execute(text("SELECT version_number, clean FROM ai_document_writes"
                              " WHERE document_id = :d"), {"d": doc_id}).fetchall()
    finally:
        s.close()


def test_edit_of_a_trusted_document_runs_without_a_card_and_is_recorded(db, monkeypatch):
    d = _doc(db, [("ai", "Fruiting: 22-26 °C")])
    uct.record_ai_document_write({"doc_id": d.id, "version": 1}, clean=True)
    executed = []
    cards = _run_edit_turn(monkeypatch, d, executed)
    assert executed == ["update_document"] and not cards
    assert sorted((v, bool(c)) for v, c in _clean_writes(db, d.id)) == [(1, True), (2, True)]


def test_minimal_document_prompt_follows_document_trust(db):
    from src.agent_loop import _minimal_odysseus_doc_messages

    trusted = _doc(db, [("ai", "Fruiting: 22-26 °C")])
    uct.record_ai_document_write({"doc_id": trusted.id, "version": 1}, clean=True)
    imported = _doc(db, [("user", "pasted from a web page")])
    for doc, allowed in ((trusted, True), (imported, False)):
        messages = _minimal_odysseus_doc_messages(
            [{"role": "user", "content": "edit this"}], doc,
        )
        assert _gate_allows_write(messages) is allowed


def test_edit_of_an_untrusted_document_still_needs_approval(db, monkeypatch):
    d = _doc(db, [("user", "pasted from a web page")])
    executed = []
    cards = _run_edit_turn(monkeypatch, d, executed)
    assert executed == [] and cards
    assert _clean_writes(db, d.id) == []
