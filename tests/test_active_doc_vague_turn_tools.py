"""Vague/continuation turns with an open document keep the edit tools.

Regression test for docs/resolvedissues.md, "Active-doc turns losing edit
tools on low-signal input" — fixed 2026-07-18, no longer an open item. With a
document active, a short confirmation ("yes and include sources") classified
low_signal=True, domains=[] and went down the RAG tool path WITHOUT
edit_document/update_document, so the model created a DUPLICATE document
instead of updating the active one (observed live on the 9B run 2026-07-17).

The agent loop now consults _vague_turn_keeps_active_document() whenever
_turn_targets_active_document() says False; these tests pin the combined
decision for the observed failure input and its guard rails.

Uses the same mock-import scaffold as test_agent_loop.py.
"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

_MOCKED_IMPORTS = [
    'sqlalchemy', 'sqlalchemy.orm', 'sqlalchemy.ext', 'sqlalchemy.ext.declarative',
    'sqlalchemy.ext.hybrid', 'sqlalchemy.sql', 'sqlalchemy.sql.expression',
    'src.database',
    'src.agent_tools',
    'core.models', 'core.database',
]
_INJECTED_IMPORT_STUBS = {}
_PREEXISTING_AGENT_LOOP = sys.modules.get("src.agent_loop")


def _drop_module_if_same(name, expected):
    if sys.modules.get(name) is expected:
        sys.modules.pop(name, None)
    parent_name, _, attr = name.rpartition(".")
    parent = sys.modules.get(parent_name)
    if parent is not None and getattr(parent, "__dict__", {}).get(attr) is expected:
        delattr(parent, attr)


for mod in _MOCKED_IMPORTS:
    if mod not in sys.modules:
        stub = MagicMock()
        sys.modules[mod] = stub
        _INJECTED_IMPORT_STUBS[mod] = stub

_IMPORTED_AGENT_LOOP = None
try:
    from src.agent_loop import (
        _classify_agent_request,
        _turn_targets_active_document,
        _vague_turn_keeps_active_document,
    )
    _IMPORTED_AGENT_LOOP = sys.modules.get("src.agent_loop")
finally:
    if _PREEXISTING_AGENT_LOOP is None and _IMPORTED_AGENT_LOOP is not None:
        _drop_module_if_same("src.agent_loop", _IMPORTED_AGENT_LOOP)
    for _mod, _stub in _INJECTED_IMPORT_STUBS.items():
        _drop_module_if_same(_mod, _stub)


def _doc(content="# Pink oyster growth phases\n\nSpawn run...", title="Growth phases"):
    return SimpleNamespace(
        current_content=content, title=title, language="markdown",
    )


def _messages(last_user):
    """Existing conversation: a prior user turn, an assistant turn, latest user."""
    return [
        {"role": "user", "content": "research pink oyster growth phases and write a document"},
        {"role": "assistant", "content": "Done — created the document."},
        {"role": "user", "content": last_user},
    ]


def _decide(last_user, active_document, existing_conversation=True):
    """Mirror the agent loop's combined active-doc decision."""
    intent = _classify_agent_request(_messages(last_user), last_user)
    relevant = _turn_targets_active_document(intent, last_user, active_document)
    if not relevant and _vague_turn_keeps_active_document(
        intent, last_user, active_document, existing_conversation
    ):
        relevant = True
    return intent, relevant


def test_observed_failure_input_keeps_document_tools():
    """"yes and include sources" — the live 2026-07-17 failure — must keep the doc."""
    intent, relevant = _decide("yes and include sources", _doc())
    assert relevant is True


def test_terse_confirmation_keeps_document_tools():
    for text in ("yes", "ok do it", "go ahead", "sure"):
        _intent, relevant = _decide(text, _doc())
        assert relevant is True, f"{text!r} with open doc must keep doc tools"


def test_casual_greeting_does_not_inherit_document():
    _intent, relevant = _decide("hey", _doc())
    assert relevant is False


def test_no_active_document_stays_irrelevant():
    _intent, relevant = _decide("yes and include sources", None)
    assert relevant is False


def test_first_turn_does_not_inherit_document():
    """Not an existing conversation -> no stale-doc inheritance."""
    text = "yes"
    intent = _classify_agent_request([{"role": "user", "content": text}], text)
    relevant = _turn_targets_active_document(intent, text, _doc())
    if not relevant:
        relevant = _vague_turn_keeps_active_document(intent, text, _doc(), False)
    assert relevant is False


def test_explicit_domain_turn_unaffected():
    """A clearly non-document request must not drag doc tools in via the helper."""
    text = "search the web for the weather in Munich tomorrow"
    intent = _classify_agent_request(_messages(text), text)
    assert intent["low_signal"] is False
    relevant = _turn_targets_active_document(intent, text, _doc())
    if not relevant:
        assert _vague_turn_keeps_active_document(intent, text, _doc(), True) is False


def test_explicit_edit_phrasing_still_matches_directly():
    """Sanity: the pre-existing direct matcher keeps working."""
    text = "fix the temperature section in the document"
    intent = _classify_agent_request(_messages(text), text)
    assert _turn_targets_active_document(intent, text, _doc()) is True
