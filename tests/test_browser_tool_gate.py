"""The built-in browser goes out only when asked for, and can be switched off.

notes/todo.md item 51. Measured 2026-10-04: the built-in Playwright MCP server
exposes 31 tools (~6k tokens of schemas, ~1.5k of prompt text). Embedding
retrieval put one of them into 53 of 489 recorded agent turns ("oh hi mark"
retrieved browser_hover), `_expand_browser_mcp_tools` then sent all 31, and no
browser tool had ever been called. Separately, `builtin_browser` in a disabled
list — what the admin panel, the `can_use_browser` privilege and
`manage_settings` write — matched no tool name, so it disabled nothing.

Covered here:
  * the narrow intent pattern, incl. the two recorded false positives of the
    pattern it replaced ("fill index.html with …");
  * `builtin_browser` expanding to every connected browser tool (incl. the 19
    that the 12-name denylist missed, e.g. browser_run_code_unsafe);
  * the real McpManager dropping withheld tools from BOTH the schemas and the
    prompt text, which is what covers every schema branch of the loop;
  * end-to-end through stream_agent_loop with a fake model call.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest

import src.agent_loop as al
import src.tool_index as tool_index
from src.mcp_manager import McpManager
from src.tool_policy import (
    BROWSER_INTENT_RE,
    BROWSER_SERVER_ID,
    BROWSER_TOOL_PREFIX,
    has_browser_intent,
    is_browser_tool_name,
)

BROWSER_TOOLS = ["browser_navigate", "browser_hover", "browser_run_code_unsafe"]
QUALIFIED = {BROWSER_TOOL_PREFIX + t for t in BROWSER_TOOLS}


# ── intent pattern ────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "open https://example.com in the browser and take a screenshot",
    "use the browser to check the page",
    "take a screenshot of the dashboard at 192.168.0.185",
    "fill out the contact form on that site",
    "I filled out the form, shall I submit the form?",
    "click the login button",
    "log in to the portal and download the invoice",
    "run it headless with playwright",
])
def test_browser_requests_are_recognised(text):
    assert has_browser_intent(text)


@pytest.mark.parametrize("text", [
    # The two recorded false positives of the replaced pattern (2026-07).
    "fill index.html with pure html extracted out of martha9_1.ino",
    "fill index.html with extracted code (html, css, javascript) out of martha9_1.ino",
    "add an onclick handler to the button",
    "what is the current value of gold in euro and how did it change over the last year?",
    "oh hi mark",
    "browse the web for news",          # a web search, not browser automation
    "home automation with the esp32",
    "submit a PR for this",
    "click here",
    "",
])
def test_ordinary_requests_are_not_browser_requests(text):
    assert not has_browser_intent(text)


def test_non_strings_are_not_intent():
    assert not has_browser_intent(None)
    assert not has_browser_intent(["browser"])


def test_tool_name_helper():
    assert is_browser_tool_name(BROWSER_SERVER_ID)
    assert is_browser_tool_name(BROWSER_TOOL_PREFIX + "browser_hover")
    assert not is_browser_tool_name("web_fetch")
    assert not is_browser_tool_name(None)


# ── a real McpManager with fake tool data ─────────────────────────────────

def _mgr():
    m = McpManager()
    m._connections = {
        BROWSER_SERVER_ID: {"name": "Built-in: Browser", "status": "connected"},
        "miniflux": {"name": "Miniflux", "status": "connected"},
    }
    m._tools = {
        BROWSER_SERVER_ID: [
            {"name": t, "description": f"{t} description", "input_schema": {"type": "object", "properties": {"x": {"type": "string"}}}}
            for t in BROWSER_TOOLS
        ],
        "miniflux": [{"name": "list_feeds", "description": "List RSS feeds", "input_schema": {}}],
    }
    return m


def _schema_names(schemas):
    return {(s.get("function") or {}).get("name") or s.get("name") for s in (schemas or [])}


# ── Fix 1: the server-wide switch ─────────────────────────────────────────

def test_disable_token_expands_to_every_connected_browser_tool():
    disabled = {BROWSER_SERVER_ID, "bash"}
    mcp_map = {"miniflux": {"list_feeds"}}
    assert al._apply_browser_disable(disabled, mcp_map, _mgr()) is True
    assert QUALIFIED <= disabled                      # incl. browser_run_code_unsafe
    assert mcp_map[BROWSER_SERVER_ID] == set(BROWSER_TOOLS)
    assert mcp_map["miniflux"] == {"list_feeds"}      # other servers untouched
    assert "bash" in disabled


def test_no_token_changes_nothing():
    disabled = {"bash"}
    mcp_map = {}
    assert al._apply_browser_disable(disabled, mcp_map, _mgr()) is False
    assert disabled == {"bash"} and mcp_map == {}


def test_disable_without_mcp_manager_still_reports_disabled():
    disabled = {BROWSER_SERVER_ID}
    assert al._apply_browser_disable(disabled, {}, None) is True
    assert disabled == {BROWSER_SERVER_ID}


def test_withheld_browser_leaves_both_schemas_and_prompt_text():
    """One map entry covers the native tool list AND the MCP text block — the
    two outputs every schema branch of the loop is built from."""
    m = _mgr()
    names = al._browser_tool_names(m)
    assert names == QUALIFIED
    withheld = al._withhold_browser({"miniflux": set()}, names)

    schemas = _schema_names(m.get_all_openai_schemas(withheld))
    assert schemas.isdisjoint(QUALIFIED)
    assert "mcp__miniflux__list_feeds" in schemas

    text = m.get_tool_descriptions_for_prompt(withheld)
    assert BROWSER_TOOL_PREFIX not in text
    assert "mcp__miniflux__list_feeds" in text

    # ...and the original map is not mutated.
    assert al._withhold_browser({}, names) is not None
    assert BROWSER_SERVER_ID not in {"miniflux": set()}


def test_unwithheld_map_still_describes_the_browser():
    # Negative control for the test above: without the entry, both outputs
    # carry the browser — so the assertion above is not vacuous.
    m = _mgr()
    assert QUALIFIED <= _schema_names(m.get_all_openai_schemas({}))
    assert BROWSER_TOOL_PREFIX in m.get_tool_descriptions_for_prompt({})


# ── end to end through stream_agent_loop ─────────────────────────────────

def _collect(gen):
    async def _run():
        return [c async for c in gen]
    return asyncio.run(_run())


class _FakeIndex:
    """Retrieval that returns a browser tool for anything — the observed noise."""
    def index_mcp_tools(self, *a, **k):
        return None

    def get_tools_for_query(self, query, k=8, always_include=None):
        return set(tool_index.ALWAYS_AVAILABLE) | {"web_search", BROWSER_TOOL_PREFIX + "browser_hover"}


def _run_turn(monkeypatch, message, **kwargs):
    sent = {"tools": None, "messages": None}

    async def _fake_stream(_candidates, messages, **kw):
        if sent["tools"] is None:
            sent["tools"] = kw.get("tools")
            sent["messages"] = messages
        yield "data: " + json.dumps({"delta": "ok"}) + "\n\n"
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(al, "get_setting", lambda key, default=None: default, raising=False)
    monkeypatch.setattr(al, "get_mcp_manager", lambda: _mgr(), raising=False)
    # Without this the loop treats the caller as a non-admin user and drops the
    # MCP manager entirely — every "browser absent" assertion would then pass
    # for the wrong reason. The miniflux check in each test guards that.
    monkeypatch.setattr(al, "blocked_tools_for_owner", lambda owner: set(), raising=False)
    monkeypatch.setattr(al, "_load_mcp_disabled_map", lambda: {}, raising=False)
    monkeypatch.setattr(al, "estimate_tokens", lambda *a, **k: 10, raising=False)
    monkeypatch.setattr(al, "stream_llm_with_fallback", _fake_stream, raising=False)
    monkeypatch.setattr(tool_index, "get_tool_index", lambda: _FakeIndex())

    _collect(al.stream_agent_loop(
        "https://api.openai.com/v1", "gpt-test",
        [{"role": "user", "content": message}],
        max_rounds=1, **kwargs,
    ))
    text = "\n".join(str(m.get("content")) for m in (sent["messages"] or []))
    assert "mcp__miniflux__list_feeds" in text, "MCP manager was not active — test would be vacuous"
    return _schema_names(sent["tools"]), text


def test_retrieval_noise_does_not_send_the_browser(monkeypatch):
    names, text = _run_turn(monkeypatch, "what is the current value of gold in euro?")
    assert "web_search" in names                      # the turn still got its tools
    assert names.isdisjoint(QUALIFIED)
    assert BROWSER_TOOL_PREFIX not in text            # nor the text block


def test_explicit_request_sends_the_whole_browser(monkeypatch):
    names, text = _run_turn(monkeypatch, "use the browser to open https://example.com and take a screenshot")
    assert QUALIFIED <= names
    assert BROWSER_TOOL_PREFIX in text


def test_disabled_browser_stays_off_even_when_asked(monkeypatch):
    names, text = _run_turn(
        monkeypatch, "use the browser to open https://example.com",
        disabled_tools={BROWSER_SERVER_ID},
    )
    assert names.isdisjoint(QUALIFIED)
    assert BROWSER_TOOL_PREFIX not in text


def test_route_forced_browser_follow_up_is_honoured(monkeypatch):
    # chat_routes forces the browser for "yes"/"send it" after a form turn.
    names, _ = _run_turn(
        monkeypatch, "yes, send it",
        forced_tools={BROWSER_TOOL_PREFIX + "browser_navigate"},
    )
    assert QUALIFIED <= names


def test_caller_supplied_tool_set_is_not_intent(monkeypatch):
    # The task scheduler fills relevant_tools from the same retrieval, so a
    # browser name in it is noise, not a request.
    names, text = _run_turn(
        monkeypatch, "summarise today's gold price",
        relevant_tools={"web_search", BROWSER_TOOL_PREFIX + "browser_hover"},
    )
    assert names.isdisjoint(QUALIFIED)
    assert BROWSER_TOOL_PREFIX not in text


# ── chat route ───────────────────────────────────────────────────────────

def test_chat_route_denylists_use_the_server_token():
    from routes import chat_routes as cr
    assert BROWSER_SERVER_ID in cr._BROWSER_DISABLE
    assert cr._BROWSER_MCP_TOOLS < cr._BROWSER_DISABLE
    assert cr._RECENT_BROWSER_CONTEXT_RE is BROWSER_INTENT_RE


def _sess(*texts):
    return SimpleNamespace(history=[{"role": "assistant", "content": t} for t in texts])


def test_short_follow_up_after_a_form_turn_still_counts():
    from routes import chat_routes as cr
    assert cr._is_contextual_browser_followup(
        "yes", _sess("I filled out the contact form. Shall I submit the form?"))


def test_short_follow_up_after_unrelated_click_talk_does_not():
    from routes import chat_routes as cr
    # The replaced context pattern matched "click"/"automation" here.
    assert not cr._is_contextual_browser_followup(
        "yes", _sess("Home automation: add an onclick handler, then click Save in the ESP32 sketch."))


# ── admin panel ──────────────────────────────────────────────────────────

def _list_tools_route():
    from routes import model_routes
    router = model_routes.setup_model_routes(model_discovery=None)
    for route in router.routes:
        if getattr(route, "path", "") == "/api/tools" and "GET" in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError("GET /api/tools not found")


@pytest.mark.parametrize("disabled,enabled", [([], True), ([BROWSER_SERVER_ID], False)])
def test_tools_panel_lists_one_browser_row(monkeypatch, disabled, enabled):
    from routes import model_routes
    monkeypatch.setattr(model_routes, "_load_settings", lambda: {"disabled_tools": disabled})
    rows = [t for t in _list_tools_route()()["tools"] if t["id"] == BROWSER_SERVER_ID]
    assert rows == [{"id": BROWSER_SERVER_ID, "enabled": enabled}]
