"""Hide routine uvicorn access-log lines from the terminal, by status code.

docs/todo.md item 13: every request prints, so real errors scroll away —
worst while the UI polls (`/api/research/status/<id>`,
`/api/chat/stream_status/<id>`). `--no-access-log` would also drop the 4xx/5xx
lines, which are the point, so this filters by status instead.

The ``access_log_hide_statuses`` setting lists what to hide. An entry is a
status (``200`` or ``"200"``, any method) or ``"METHOD STATUS"`` (``"GET 200"``
— keeps PUT/POST/DELETE 200s visible, e.g. while confirming editor saves).
The default hides 200 only; 304 is left visible on purpose, since a 304 storm
is how a stale-cache bug shows itself — add it to the list to hide it too.
``[]`` shows everything. Read through ``get_setting`` (2 s cache), so a change
applies without a restart.

Access lines do not reach ``data/logs/app.log`` (uvicorn's ``uvicorn.access``
logger does not propagate), so this changes the terminal only.
"""
import logging

ACCESS_LOGGER_NAME = "uvicorn.access"
SETTING_KEY = "access_log_hide_statuses"


def _record_method_status(record: logging.LogRecord):
    """(METHOD, status) from a uvicorn access record, or None for any other
    record. uvicorn logs ``'%s - "%s %s HTTP/%s" %d'`` with args
    (client, method, path, http_version, status)."""
    args = record.args
    if not isinstance(args, tuple) or len(args) != 5:
        return None
    method, status = args[1], args[4]
    if isinstance(status, bool):
        return None
    try:
        return str(method).upper(), int(status)
    except (TypeError, ValueError):
        return None


def _parse_rules(raw):
    """Setting value -> (statuses hidden for every method, {(METHOD, status)}).
    Entries that don't parse are ignored rather than hiding anything."""
    any_method, per_method = set(), set()
    if not isinstance(raw, (list, tuple, set)):
        return any_method, per_method
    for entry in raw:
        if isinstance(entry, bool):
            continue
        if isinstance(entry, int):
            any_method.add(entry)
            continue
        if not isinstance(entry, str):
            continue
        parts = entry.split()
        try:
            if len(parts) == 1:
                any_method.add(int(parts[0]))
            elif len(parts) == 2:
                per_method.add((parts[0].upper(), int(parts[1])))
        except ValueError:
            continue
    return any_method, per_method


class AccessLogStatusFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        ms = _record_method_status(record)
        if ms is None:
            return True
        try:
            from src.settings import get_setting
            raw = get_setting(SETTING_KEY, [200])
        except Exception:
            return True  # settings unreadable: show everything
        any_method, per_method = _parse_rules(raw)
        method, status = ms
        return status not in any_method and (method, status) not in per_method


def install_access_log_filter(logger_name: str = ACCESS_LOGGER_NAME) -> AccessLogStatusFilter:
    """Attach the filter to the access logger once. Safe to call repeatedly.

    Logger filters survive uvicorn's own ``dictConfig`` (it replaces handlers,
    not filters), so this works whether uvicorn configures logging before the
    app is imported (``uvicorn app:app``) or after (``uvicorn.run(app)``)."""
    lg = logging.getLogger(logger_name)
    for f in lg.filters:
        if isinstance(f, AccessLogStatusFilter):
            return f
    f = AccessLogStatusFilter()
    lg.addFilter(f)
    return f
