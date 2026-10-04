""""SMTP/IMAP not configured" is logged once, not on every config read.

The email poller reads the config every minute, so an instance with no email
account printed two warnings a minute to the terminal and to app.log (seen
live 2026-10-04, docs/todo.md item 13). Now: one WARNING per (protocol,
account) per process, later reads log at DEBUG, and a key is forgotten when
that protocol becomes configured so breaking it again warns again.
"""
import logging

import pytest

import routes.email_helpers as eh

_ENV = ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "IMAP_HOST", "IMAP_USER", "IMAP_PASSWORD")
_FULL = {
    "smtp_host": "smtp.example.org", "smtp_user": "u", "smtp_password": "p",
    "imap_host": "imap.example.org", "imap_user": "u", "imap_password": "p",
}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for k in _ENV:
        monkeypatch.delenv(k, raising=False)
    eh._NOT_CONFIGURED_WARNED.clear()
    yield
    eh._NOT_CONFIGURED_WARNED.clear()


def _warnings(caplog, word):
    return [r for r in caplog.records
            if r.levelno == logging.WARNING and f"{word} not configured" in r.getMessage()]


def _legacy_config(monkeypatch, settings):
    """Drive the legacy (settings.json / env) branch: no email_accounts rows."""
    monkeypatch.setattr(eh, "_load_settings", lambda: dict(settings))

    class _NoAccounts:
        def __call__(self):
            raise RuntimeError("no database in this test")

    import core.database as cdb
    monkeypatch.setattr(cdb, "SessionLocal", _NoAccounts())
    return eh._get_email_config()


def test_unconfigured_warns_once_per_protocol(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG, logger=eh.logger.name)
    for _ in range(5):  # five poller minutes
        _legacy_config(monkeypatch, {})
    assert len(_warnings(caplog, "SMTP")) == 1
    assert len(_warnings(caplog, "IMAP")) == 1
    later = [r for r in caplog.records if r.levelno == logging.DEBUG and "not configured" in r.getMessage()]
    assert len(later) == 8  # still recorded, at DEBUG


def test_configured_is_silent(monkeypatch, caplog):
    """Negative control: a configured account never warns, so the test above
    is counting the right thing."""
    caplog.set_level(logging.DEBUG, logger=eh.logger.name)
    for _ in range(3):
        _legacy_config(monkeypatch, _FULL)
    assert not [r for r in caplog.records if "not configured" in r.getMessage()]


def test_breaking_it_again_warns_again(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger=eh.logger.name)
    _legacy_config(monkeypatch, {})
    _legacy_config(monkeypatch, _FULL)
    _legacy_config(monkeypatch, {})
    assert len(_warnings(caplog, "SMTP")) == 2


def test_accounts_are_tracked_separately(caplog):
    caplog.set_level(logging.WARNING, logger=eh.logger.name)
    for _ in range(3):
        eh._note_email_configured("SMTP", "acct-a", False, "SMTP not configured for account 'a'")
        eh._note_email_configured("SMTP", "acct-b", False, "SMTP not configured for account 'b'")
    assert sorted(r.getMessage() for r in _warnings(caplog, "SMTP")) == [
        "SMTP not configured for account 'a'", "SMTP not configured for account 'b'",
    ]
