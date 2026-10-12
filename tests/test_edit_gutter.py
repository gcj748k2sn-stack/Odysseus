"""edit_document: a line-number gutter copied into REPLACE is not written into the document.

Covers ``src/edit_gutter.py`` and its call site in the FIND-without-gutter
fallback of ``edit_document`` (``src/agent_tools/document_tools.py``).
Benchmark 2026-10-10 (Qwen, ``document_followup`` r1): FIND "3\\t- map",
REPLACE "3\\t- map\\n4\\t- headlamp" left the list with two bullets.
"""
import asyncio
import sys
import types

import pytest

from src.agent_tools import TOOL_HANDLERS
from src.agent_tools.document_tools import set_active_document
from src.agent_tools import document_tools as _DT
from src.edit_gutter import strip


class _Col:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return (self.name, "eq", other)

    def desc(self):
        return self


class _Doc:
    id = _Col("id")
    owner = _Col("owner")
    is_active = _Col("is_active")
    title = _Col("title")
    language = _Col("language")
    updated_at = _Col("updated_at")


class _Version:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Query:
    def __init__(self, doc):
        self.doc = doc

    def filter(self, *a):
        return self

    def order_by(self, *a):
        return self

    def limit(self, *a):
        return self

    def first(self):
        return self.doc

    def all(self):
        return [self.doc]


class _Db:
    def __init__(self, doc):
        self.q = _Query(doc)

    def query(self, *a):
        return self.q

    def add(self, *a):
        pass

    def commit(self):
        pass

    def refresh(self, *a):
        pass

    def close(self):
        pass


def _edit(monkeypatch, content, block):
    doc = types.SimpleNamespace(id="d1", owner="alice", is_active=True, title="Day pack", language="markdown",
                                current_content=content, version_count=1)
    mod = types.ModuleType("src.database")
    mod.SessionLocal = lambda: _Db(doc)
    mod.Document, mod.DocumentVersion, mod.Session = _Doc, _Version, object
    monkeypatch.setitem(sys.modules, "src.database", mod)
    monkeypatch.setattr(_DT, "_missing_document_upload", lambda owner, c: None)
    set_active_document("d1")
    try:
        result = asyncio.run(TOOL_HANDLERS["edit_document"](block, {"owner": "alice"}))
    finally:
        set_active_document(None)
    return doc, result


LIST = "- water bottle\n- rain jacket\n- map"


def test_gutter_copied_into_find_and_replace_leaves_a_clean_list(monkeypatch):
    doc, result = _edit(monkeypatch, LIST, "<<<FIND>>>\n3\t- map\n<<<REPLACE>>>\n3\t- map\n4\t- headlamp\n<<<END>>>")
    assert result.get("applied") == 1, result
    assert doc.current_content == "- water bottle\n- rain jacket\n- map\n- headlamp"


def test_exact_find_keeps_replace_as_written(monkeypatch):
    """Negative control: without the fallback, REPLACE is never touched."""
    doc, result = _edit(monkeypatch, "a\n1\tb", "<<<FIND>>>\na\n<<<REPLACE>>>\na\n2\tc\n<<<END>>>")
    assert result.get("applied") == 1, result
    assert doc.current_content == "a\n2\tc\n1\tb"


def test_strip():
    assert strip("3\t- map\n4\t- headlamp") == "- map\n- headlamp"
    assert strip("no gutter\n\tindented") == "no gutter\n\tindented"
    assert strip("") == "" and strip(None) == ""
