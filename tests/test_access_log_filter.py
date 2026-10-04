"""Terminal access-log noise (docs/todo.md item 13).

Routine 200s are hidden from the uvicorn access log by status code; 4xx/5xx
and (by default) 304 stay visible. Records are produced through the real
``uvicorn.access`` logger with uvicorn's own format and argument order.
"""
import ast
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from src import access_log_filter as alf
from src.settings import DEFAULT_SETTINGS

ROOT = Path(__file__).resolve().parents[1]


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


@pytest.fixture
def access_logger():
    lg = logging.getLogger(alf.ACCESS_LOGGER_NAME)
    saved = (list(lg.filters), list(lg.handlers), lg.level, lg.propagate)
    for f in list(lg.filters):
        lg.removeFilter(f)
    cap = _Capture()
    lg.handlers = [cap]
    lg.setLevel(logging.INFO)
    lg.propagate = False
    alf.install_access_log_filter()
    yield lg, cap
    lg.filters[:] = saved[0]
    lg.handlers = saved[1]
    lg.setLevel(saved[2])
    lg.propagate = saved[3]


def _log(lg, method, status, path="/api/chat/stream_status/abc"):
    # uvicorn/protocols/http/{h11,httptools}_impl.py
    lg.info('%s - "%s %s HTTP/%s" %d', "127.0.0.1:50000", method, path, "1.1", status)


def _with_setting(value):
    return patch("src.settings.get_setting",
                 side_effect=lambda key, default=None: value if key == alf.SETTING_KEY else default)


def test_default_hides_200_only():
    assert DEFAULT_SETTINGS[alf.SETTING_KEY] == [200]


def test_default_setting_hides_200_and_keeps_errors_and_304(access_logger):
    lg, cap = access_logger
    with _with_setting(DEFAULT_SETTINGS[alf.SETTING_KEY]):
        for method, status in [("GET", 200), ("PUT", 200), ("GET", 304),
                               ("PUT", 404), ("POST", 500), ("GET", 307)]:
            _log(lg, method, status)
    assert [l.split('"')[1].split()[0] + " " + l.rsplit(" ", 1)[1] for l in cap.lines] == [
        "GET 304", "PUT 404", "POST 500", "GET 307",
    ]


def test_empty_setting_shows_everything(access_logger):
    """Negative control: with nothing configured the filter must not hide a
    200 — so the test above depends on the setting, not on the filter
    dropping 200s unconditionally."""
    lg, cap = access_logger
    with _with_setting([]):
        _log(lg, "GET", 200)
        _log(lg, "GET", 304)
    assert len(cap.lines) == 2


def test_304_hidden_only_when_listed(access_logger):
    lg, cap = access_logger
    with _with_setting([200, "304"]):
        _log(lg, "GET", 304)
        _log(lg, "GET", 404)
    assert len(cap.lines) == 1 and cap.lines[0].endswith(" 404")


def test_method_specific_entry_keeps_writes_visible(access_logger):
    lg, cap = access_logger
    with _with_setting(["get 200"]):
        _log(lg, "GET", 200)
        _log(lg, "PUT", 200, path="/api/documents/d1")
    assert len(cap.lines) == 1 and '"PUT /api/documents/d1' in cap.lines[0]


@pytest.mark.parametrize("bad", [None, "200", 200, {"200": True}, [True, None, "x", "GET", "GET 2xx", 1.5]])
def test_malformed_setting_hides_nothing(access_logger, bad):
    lg, cap = access_logger
    with _with_setting(bad):
        _log(lg, "GET", 200)
    assert len(cap.lines) == 1


def test_unreadable_settings_show_everything(access_logger):
    lg, cap = access_logger
    with patch("src.settings.get_setting", side_effect=RuntimeError("boom")):
        _log(lg, "GET", 200)
    assert len(cap.lines) == 1


def test_non_access_records_pass_untouched(access_logger):
    lg, cap = access_logger
    with _with_setting([200]):
        lg.info("plain message")
        lg.info("%s and %s", "two", "args")
        lg.info('%s - "%s %s HTTP/%s" %s', "c", "GET", "/", "1.1", "not-a-status")
    assert len(cap.lines) == 3


def test_install_is_idempotent(access_logger):
    lg, _ = access_logger
    first = alf.install_access_log_filter()
    assert alf.install_access_log_filter() is first
    assert sum(isinstance(f, alf.AccessLogStatusFilter) for f in lg.filters) == 1


def test_filter_survives_uvicorn_logging_config(access_logger):
    """`uvicorn.run(app)` configures logging AFTER app.py has installed the
    filter; dictConfig must not drop it."""
    uvicorn_config = pytest.importorskip("uvicorn.config")
    lg, _ = access_logger
    saved = (list(lg.handlers), lg.propagate)
    try:
        uvicorn_config.Config(app="app:app", log_level="info")  # runs configure_logging()
        assert any(isinstance(f, alf.AccessLogStatusFilter) for f in lg.filters)
    finally:
        lg.handlers, lg.propagate = saved


def test_app_module_installs_it():
    """Every launch path (app.py __main__, launcher.py, start-macos.sh,
    Dockerfile, odysseus-ui.service) imports app.py, so app.py is where it is
    wired. Checked on the source: importing app.py runs startup migrations."""
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    calls = [
        n for n in tree.body
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
        and getattr(n.value.func, "id", None) == "install_access_log_filter"
    ]
    assert calls, "app.py must call install_access_log_filter() at module level"
