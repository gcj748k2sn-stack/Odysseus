"""What a turn reports, to the reader and to the record.

Fork-only code moved out of ``src/agent_loop.py`` so that upstream's agent loop
carries call sites instead of bodies (smaller merge surface). Behaviour is
unchanged by the move; ``stream_agent_loop`` calls:

- ``doc_tool_result_landed``  - whether a document tool result counts as done
- ``record_doc_tool_result``  - per successful document tool, in the tool loop
  and for an approved document action replayed at the start of a turn
- ``doc_tool_break_report``   - the finetune path's loop break
- ``end_of_turn_report``      - closing line and notices, after strip_tool_blocks

Logs go to the ``src.agent_loop`` logger, so ``app.log`` lines are the same as
before the move.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from src.document_fidelity import check_document
from src.known_facts import check_document as check_known_facts

logger = logging.getLogger("src.agent_loop")


def strip_tool_blocks(text, *args, **kwargs):
    """``src.agent_tools.strip_tool_blocks``, looked up per call.

    Several upstream tests import ``src.agent_loop`` with ``src.agent_tools``
    stubbed by a MagicMock and then drop the loop module again. A binding taken
    here at import time would keep that stub alive in this module for every
    later test in the process.
    """
    from src.agent_tools import strip_tool_blocks as _impl
    return _impl(text, *args, **kwargs)


def _resolved_tool_event_name(event: Dict[str, Any]) -> str:
    """Delegate to upstream's helper in ``src.agent_loop`` (lazy: import cycle)."""
    from src.agent_loop import _resolved_tool_event_name as _impl
    return _impl(event)


DOC_EDIT_RETRY_TOOLS = ("edit_document", "suggest_document", "update_document")
DOC_TOOLS = ("create_document",) + DOC_EDIT_RETRY_TOOLS

# Tools that only LOOK at things. A turn that ran nothing but these and then
# produced no text gathered information and never used it.
#
# An explicit allowlist on purpose: an unknown tool (MCP, cookbook, a future
# built-in) must NOT be assumed read-only, or the guard could tell a user their
# email wasn't sent when it was. Unknown tool in the turn -> guard stays quiet.
READ_ONLY_TOOLS = frozenset({
    "glob", "grep", "ls", "read_file", "get_workspace",
    "web_search", "web_fetch",
    "search_chats", "manage_documents",
    "list_downloads", "list_models", "list_served_models", "list_sessions",
    "resolve_contact",
})


def _gathering_only_notice(tool_events: list) -> str:
    """Notice for a turn that only gathered information and then said nothing.

    Without it such a turn was saved as a bare "Done." - a false success.
    Returns "" when the turn used any tool that might have changed something,
    or any tool not in READ_ONLY_TOOLS.

    Must run AFTER strip_tool_blocks: before stripping, the tool fence makes
    the turn look as if it produced text the user never sees.
    """
    names = [ev.get("tool") or "" for ev in (tool_events or [])]
    seen = [n for n in dict.fromkeys(names) if n]
    if not seen or any(n not in READ_ONLY_TOOLS for n in seen):
        return ""
    listed = ", ".join(f"`{n}`" for n in seen)
    return (
        f"I ran {listed} and then stopped without producing an answer — "
        "**nothing was created or changed.** The information was gathered but "
        "never used. The results were not kept, so send the request again to "
        "rerun it."
    )


# Tools whose output the end-of-turn path in stream_agent_loop already promotes
# into the reply verbatim (manage_notes / manage_calendar / manage_tasks /
# list_emails / read_email). That block REPLACES full_response, so anything
# appended before it would be discarded.
#
# Known gap: a manage_notes create is a side effect and stays unreported
# (notes: "Non-document tools reported nothing at all").
_SELF_REPORTING_TOOLS = frozenset({
    "manage_notes", "manage_calendar", "manage_tasks",
    "list_emails", "read_email",
    "mcp__email__list_emails", "mcp__email__read_email",
})


def doc_tool_result_landed(result: Dict[str, Any]) -> bool:
    """True when a document tool actually ran and did not fail.

    An approval placeholder ("Waiting for an exact user approval.") carries no
    ``error`` key, yet nothing ran; counting it reported an edit that never
    happened (notes: "A document edit waiting on an approval card is reported
    as done").
    """
    return bool(
        isinstance(result, dict)
        and not result.get("error")
        and not result.get("approval_required")
    )


def _awaiting_approval(event: Dict[str, Any]) -> bool:
    """True for a tool event that stopped at an approval card and did not run."""
    card = event.get("ask_user")
    return isinstance(card, dict) and card.get("kind") == "tool_approval"


def _tool_event_failed(event: Dict[str, Any]) -> bool:
    """True when a tool event carries a non-zero exit code.

    Document tools record exit_code=None on success, so None means "no
    verdict", never failure.
    """
    code = event.get("exit_code")
    return isinstance(code, int) and not isinstance(code, bool) and code != 0


def _first_line(text: Any, limit: int = 180) -> str:
    """First non-empty line of a tool's output, truncated for a closing line."""
    for line in str(text or "").splitlines():
        line = line.strip()
        if line:
            return line[:limit] + ("…" if len(line) > limit else "")
    return ""


def _side_effect_tool_summary(tool_events: list, failures_only: bool = False) -> str:
    """Closing report for a turn that ran a side-effecting NON-document tool.

    Built from the tool result, like _doc_tool_summary, not from another model
    round. It reports the RESULT, not the call: a refused write_file looks like
    a write in the tool sequence (notes: "Non-document tools reported nothing
    at all").

    Coverage is the inverse of READ_ONLY_TOOLS: anything not known-read-only,
    not a document tool and not self-reporting gets a line, including MCP and
    future tools. The failure modes are not symmetric: a wrong guess here costs
    one extra line; a wrong guess in READ_ONLY_TOOLS would hide real work.

    failures_only mirrors _doc_tool_summary(warnings_only=True): a confident
    model summary must not suppress the report of a tool that failed. Successes
    are reported only when the model said nothing; failures always.

    Report-only. It never asks the model to act (see the reverted stall nudge
    in stream_agent_loop).
    """
    lines = []
    for event in tool_events or []:
        name = _resolved_tool_event_name(event)
        if not name:
            continue
        if name in READ_ONLY_TOOLS or name in DOC_TOOLS or name in _SELF_REPORTING_TOOLS:
            continue
        if _awaiting_approval(event):
            # Nothing ran; the card on screen is the report.
            continue
        detail = _first_line(event.get("output"))
        if _tool_event_failed(event):
            lines.append(
                f"⚠️ **`{name}` failed** — {detail or 'no reason was returned'}"
            )
        elif failures_only:
            continue
        elif name == "write_file":
            # The tool's own output is already "Wrote N bytes to <path>".
            lines.append(detail or "Ran `write_file`")
            if re.match(r"^wrote 0 bytes\b", detail, re.I):
                lines.append(
                    "⚠️ **That file is empty** — 0 bytes were written, so "
                    "whatever it held before is gone."
                )
        else:
            lines.append(f"Ran `{name}`" + (f" — {detail}" if detail else ""))
    if not lines:
        return ""
    if len(lines) == 1:
        return lines[0]
    return "\n".join(f"- {line}" for line in lines)


def _unstarted_promise_notice(full_response: str, tool_events: list) -> str:
    """Notice for a turn that announced work, called nothing, and stopped.

    Neither _gathering_only_notice (needs a tool to have run) nor
    _text_is_only_preamble (needs a tool boundary) can see a zero-tool turn.

    Lexical on purpose: no tool ran, so "nothing was created or changed" is a
    fact, and a trailing colon shows the message stopped mid-thought.
    Deliberately narrow - an intent regex matched turns that were fine (notes:
    "The agent gathers information, then stops").
    """
    if tool_events:
        return ""
    body = strip_tool_blocks(full_response or "").strip()
    if not body or not body.endswith(":"):
        return ""
    return (
        "…and then I stopped there — **nothing was created or changed, and I "
        "called no tools this turn.** That sentence was the setup, not the "
        "work. Ask me again and I'll do it."
    )


_PAYLOAD_FENCE_OPEN_RE = re.compile(r"```([A-Za-z0-9_-]*)[^\n]*\n")


def _fenced_regions(text: str):
    """Yield (tag, body) for every fence, INCLUDING an unterminated trailing one.

    The unterminated branch is defensive: every recorded instance closed its
    fence. It stays because a turn cut off mid-payload is the same failure with
    a truncated tail.
    """
    pos = 0
    while True:
        m = _PAYLOAD_FENCE_OPEN_RE.search(text, pos)
        if not m:
            return
        end = text.find("```", m.end())
        yield m.group(1).lower(), (text[m.end():] if end == -1 else text[m.end():end])
        if end == -1:
            return
        pos = end + 3


def _tool_payload_looks_like_edit(body: str) -> str:
    """Lexical, deliberately NOT json.loads().

    A payload the model writes as prose is often invalid JSON (literal newlines
    inside strings), and parsing would reject exactly the malformed calls this
    exists to catch.
    """
    if "<<<FIND>>>" in body and "<<<REPLACE>>>" in body:
        return "FIND/REPLACE markers"
    if '"find"' in body and '"replace"' in body and ('"edits"' in body or '"suggestions"' in body):
        return "edits/find/replace keys"
    return ""


def _tool_payload_as_text_notice(full_response: str, tool_events: list) -> str:
    """Notice for a turn that WROTE a tool call instead of MAKING one.

    The fence tag is the dispatch key, so an edit payload in a ```json fence is
    inert display text: nothing ran, and the reply often claims success. No
    other guard sees it (they need a tool run, a trailing colon, or a tool
    boundary).

    Gated on zero tool events because with tools the payload may be an
    illustrative example. Report-only (notes: "The model wrote the tool call
    instead of making it").
    """
    if tool_events:
        return ""
    for _tag, body in _fenced_regions(full_response or ""):
        reason = _tool_payload_looks_like_edit(body)
        if reason:
            return (
                "\n\n⚠️ **I wrote that edit out as text instead of running it — "
                "nothing was created or changed.** A fenced block only executes "
                "when its tag is the tool name (```edit_document); any other tag "
                "is display text. Ask me to try again and I'll make the call "
                "properly."
            )
    return ""


def _doc_edit_retry_directive(tool: str, attempt: int) -> str:
    """Corrective instruction appended to a FAILED document-edit tool result.

    Puts the exact edit syntax at the point of failure, and escalates: a second
    failure asks for a full rewrite, which has no FIND text to get wrong.

    Still guidance, not enforcement. Tool schemas DO reach this model
    (_is_api_model is true for a tool-capable endpoint), so narrowing or
    forcing would be possible; the mechanical backstop today is the end-of-turn
    guard, which refuses to end a turn silently after an unresolved edit
    failure. Do not turn this into an "act now" nudge - that once wiped a
    document (notes: "Notes & constraints").
    """
    if attempt <= 1:
        return (
            "\n\n⚠️ THE EDIT DID NOT HAPPEN — the document is UNCHANGED. "
            "Retry NOW, in this same turn. If you write it as a fenced block, the "
            "fence tag MUST be the tool name — a ```json block is display text and "
            "runs nothing. Exactly this shape:\n"
            "```edit_document\n"
            "<<<FIND>>>\n"
            "exact text copied from the document\n"
            "<<<REPLACE>>>\n"
            "your corrected text\n"
            "<<<END>>>\n"
            "```\n"
            "Copy the FIND text verbatim from the document — same punctuation, same "
            "units, same capitalisation. Do not describe the edit in prose, and do not "
            "end the turn until an edit succeeds."
        )
    return (
        f"\n\n⚠️ {tool} has now failed {attempt} times and the document is STILL "
        "UNCHANGED. Stop trying to target individual passages — the FIND text is not "
        "matching. Call `update_document` instead and send the COMPLETE document with "
        "your corrections already applied:\n"
        "```update_document\n"
        "the entire document, corrected\n"
        "```\n"
        "This has no FIND text to match, so it cannot fail the same way. Do not end "
        "the turn without doing this."
    )


DOC_EDIT_FAILED_NOTICE = (
    "I couldn't apply the edit — **the document is unchanged.** The edit tool "
    "rejected {count} attempt{plural} this turn ({reason}). Ask me to try again and "
    "I'll rewrite the document in full instead of patching individual passages."
)


def _closing_doc_summary(
    full_response: str,
    doc_info: Dict[str, Any],
    preamble_only: bool = False,
) -> tuple:
    """Closing line for a turn that changed a document but said nothing about it.

    The model-agnostic half of the split gate (the finetune path does this at
    its loop break). Without it the turn was saved as a bare "Done." - no
    version, no edit count, no warnings.

    Fires when the response is empty, or when everything in it was written
    BEFORE the edit landed (preamble_only): an intent sentence is
    indistinguishable from a summary by length. A preamble is kept and the
    report appended to it.

    Call AFTER strip_tool_blocks.

    Returns:
        (final_response: str, chunk: str | None)
    """
    if not doc_info:
        return full_response, None
    existing = full_response.strip()
    if existing and not preamble_only:
        # The model wrote its own report, so the action line is redundant - but
        # the warning blocks are not; the model never writes those about
        # itself. See _doc_tool_summary.
        warnings = _doc_tool_summary(doc_info, warnings_only=True)
        if not warnings:
            return full_response, None
        chunk = "\n\n" + warnings
        return existing + chunk, 'data: ' + json.dumps({"delta": chunk}) + '\n\n'
    summary = _doc_tool_summary(doc_info)
    if not summary:
        return full_response, None
    if existing:
        chunk = "\n\n" + summary
        return existing + chunk, 'data: ' + json.dumps({"delta": chunk}) + '\n\n'
    return summary, 'data: ' + json.dumps({"delta": summary}) + '\n\n'


def _text_is_only_preamble(full_response: str, text_before_tool: Optional[str]) -> bool:
    """True when the model wrote nothing after its last document edit landed.

    Positional, not lexical — no keyword matching on "I'll" or "Let me", which
    would be brittle and English-only. Text written before the tool ran cannot
    be a report of what the tool did, whatever it says.
    """
    if text_before_tool is None:
        return False
    before = strip_tool_blocks(text_before_tool).strip()
    if not before:
        return False
    after = strip_tool_blocks(full_response).strip()
    if after == before:
        return True
    return after.startswith(before) and not after[len(before):].strip()


def _doc_tool_summary(info: Dict[str, Any], warnings_only: bool = False) -> str:
    """Closing line for a turn that ended on a document tool, built from the tool
    result rather than a further LLM round.

    Free (no extra round) and more reliable than asking the model to recall its
    own edits. Also surfaces skipped edits: edit_document reports success when
    at least one FIND block matched.

    warnings_only drops the "Created/Updated ..." action line and returns only
    the warning blocks (stale_values, fidelity, known_facts). Callers use it
    when the model wrote its own summary: the user was told what happened but
    not that it was wrong, and a confident summary must not withhold the
    warnings (notes: "Three S1 warnings were suppressed whenever the model
    wrote its own summary").
    """
    if not info:
        return ""
    tool = info.get("tool") or ""
    title = (info.get("title") or "").strip()
    version = info.get("version")
    applied = info.get("applied")
    skipped = info.get("skipped") or 0

    name = f"**{title}**" if title else "the document"
    ver = f" (v{version})" if version else ""

    # No early return here: the fidelity warning below applies to every tool,
    # create_document included.
    if tool == "create_document":
        line = f"Created {name}{ver}."
    elif tool == "suggest_document":
        line = f"Added suggestions to {name} — nothing changed until you accept them."
    else:
        # update_document / edit_document
        calls = info.get("calls") or 0
        rounds = f" across {calls} rounds" if calls > 1 else ""
        if applied is not None:
            line = f"Updated {name}{ver} — {applied} edit{'s' if applied != 1 else ''} applied{rounds}"
        else:
            line = f"Updated {name}{ver}"
        if skipped:
            line += (
                f", **{skipped} not applied** (the FIND text didn't match — "
                f"those corrections are still missing)"
            )
        line += "."

    # The action line and the warnings are assembled separately so a caller can
    # take the warnings alone — see `warnings_only` in the docstring.
    parts = [] if warnings_only else [line]

    # A correction applied in one place and left standing in another reads as
    # fact-checked while the document still contradicts itself. Say so plainly.
    stale = info.get("stale_values") or []
    if stale:
        shown = ", ".join(f"`{v}`" for v in stale[:6])
        more = f" (+{len(stale) - 6} more)" if len(stale) > 6 else ""
        parts.append(
            f"⚠️ **Still inconsistent** — {shown}{more} "
            f"{'was' if len(stale) == 1 else 'were'} corrected in one place but "
            f"still appear{'s' if len(stale) == 1 else ''} elsewhere in the document. "
            f"The document now contradicts itself; ask me to fix the remaining spots."
        )

    # The document disagrees with the data it was built from (notes: "The
    # document didn't match its source").
    fidelity = info.get("fidelity") or []
    if fidelity:
        shown = "\n".join(f"- {f}" for f in fidelity[:4])
        more = f"\n- (+{len(fidelity) - 4} more)" if len(fidelity) > 4 else ""
        parts.append(
            f"⚠️ **Doesn't match the source** — I checked the document "
            f"against the data I fetched:\n{shown}{more}\n\n"
            f"Worth reading before you rely on these numbers."
        )

    # Checked against facts established once and written down. Separate from
    # fidelity: a document can match its source and still be wrong about the
    # world (notes: "The document contradicted what we had already
    # established"). Flat wording on purpose - the failure is a document that
    # sounds fact-checked.
    known_facts = info.get("known_facts") or []
    if known_facts:
        shown = "\n".join(f"- {f}" for f in known_facts[:4])
        more = f"\n- (+{len(known_facts) - 4} more)" if len(known_facts) > 4 else ""
        parts.append(
            f"⚠️ **Contradicts what we already established** — checked "
            f"against `config/known_facts.json`:\n{shown}{more}\n\n"
            f"I have not re-verified these against sources; the file is the record."
        )
    return "\n\n".join(p for p in parts if p)


def _format_prompt_cache(pc: Optional[Dict[str, Any]]) -> str:
    """" prompt_tokens=... cache_n=... prompt_n=... prompt_ms=..." for the
    round_stream_done log line. "?" where the backend reported nothing;
    cached_tokens only when an OpenAI-style server sent it.
    """
    pc = pc or {}
    out = " prompt_tokens=%s cache_n=%s prompt_n=%s prompt_ms=%s" % tuple(
        pc.get(k, "?") for k in ("prompt_tokens", "cache_n", "prompt_n", "prompt_ms")
    )
    if "cached_tokens" in pc:
        out += " cached_tokens=%s" % pc["cached_tokens"]
    return out


# Ceiling on the raw tool arguments persisted with a document tool event (16 KB
# covers every real edit seen so far). Truncation is marked in-band so a replay
# can tell a clipped record from a complete one.
_PERSISTED_COMMAND_MAX = 16384
_PERSISTED_COMMAND_TRUNCATION_MARKER = "\n…[truncated by agent_loop: {dropped} more chars]"


def _cap_persisted_command(command: str) -> str:
    """Clip tool arguments for storage, marking the clip so replay can see it."""
    if command is None:
        return ""
    if len(command) <= _PERSISTED_COMMAND_MAX:
        return command
    marker = _PERSISTED_COMMAND_TRUNCATION_MARKER.format(
        dropped=len(command) - _PERSISTED_COMMAND_MAX
    )
    return command[:_PERSISTED_COMMAND_MAX] + marker


def record_doc_tool_result(
    prev_info: Dict[str, Any], tool: str, result: Dict[str, Any], tool_events: list,
) -> Dict[str, Any]:
    """Fold one successful document-tool result into the turn's report data.

    Called from the tool loop in ``stream_agent_loop`` for every model; returns
    the new ``_ody_doc_tool_info``. Runs the two report-only lints (document vs
    its source, document vs ``config/known_facts.json``) and logs their findings.
    """
    # SPLIT GATE: report data is built for EVERY model; only the loop break
    # stays behind _ody_doc_finetune_mode. Widening the whole gate would also
    # narrow the tools and break the loop on first success, killing the model's
    # own create -> edit self-correction (notes: "The document reporting path
    # was dead code on the current model").
    #
    # ACCUMULATE across edit rounds: applied/skipped are summed; title, version
    # and stale_values take the latest (they describe the document as it stands
    # now).
    def _sum(prev: Any, cur: Any) -> Any:
        if prev is None and cur is None:
            return None
        return (prev or 0) + (cur or 0)

    info = {
        "tool": tool,
        "title": result.get("title") or prev_info.get("title") or "",
        "version": result.get("version"),
        "applied": _sum(prev_info.get("applied"), result.get("applied")),
        "skipped": _sum(prev_info.get("skipped"), result.get("skipped")),
        "stale_values": result.get("stale_values") or [],
        "calls": (prev_info.get("calls") or 0) + 1,
    }
    # Does the document match the data the model was handed? Runs here, not in
    # the document tool, because only the loop sees both the earlier web_fetch
    # and the document; this also covers update_document. Report-only: a
    # checker that makes the model act on a false positive could destroy a
    # document.
    try:
        _fidelity = check_document(
            result.get("content") or "", tool_events
        )
    except Exception as _fid_err:  # never break a turn over a lint
        _fidelity = []
        logger.warning("document fidelity check failed: %s", _fid_err, exc_info=True)
    if _fidelity:
        info["fidelity"] = _fidelity
        logger.warning(
            "[agent] document does not match its source (%d finding(s)): %s",
            len(_fidelity), "; ".join(_fidelity[:3]),
        )
    # Does it match facts recorded in config/known_facts.json? Same placement
    # and report-only rule; a different question from fidelity.
    try:
        _known = check_known_facts(result.get("content") or "")
    except Exception as _kf_err:  # never break a turn over a lint
        _known = []
        logger.warning("known-facts check failed: %s", _kf_err, exc_info=True)
    if _known:
        info["known_facts"] = _known
        logger.warning(
            "[agent] document contradicts recorded ground truth (%d finding(s)): %s",
            len(_known), "; ".join(_known[:3]),
        )
    return info


def doc_tool_break_report(
    full_response: str, info: Dict[str, Any], text_before_tool: Optional[str],
) -> Tuple[str, str]:
    """Closing text for the finetune path, which breaks the loop right after a
    document tool. Returns ``(full_response, delta)``; ``delta`` is "" when
    nothing is added."""
    # Same three cases as end_of_turn_report: nothing written, a bare tool
    # fence, or prose written entirely BEFORE the edit landed (kept, report
    # appended).
    _fr = full_response.strip()
    _pre_only = _text_is_only_preamble(full_response, text_before_tool)
    if not _fr or _fr.startswith("```") or _pre_only:
        # The loop breaks here, so the model never gets a round to report the
        # edit. "Done." only if the tool told us nothing.
        _summary = _doc_tool_summary(info) or "Done."
        if _pre_only and _fr and not _fr.startswith("```"):
            _summary = "\n\n" + _summary
            full_response = _fr + _summary
        else:
            full_response = _summary
        return full_response, _summary
    # The model reported the edit itself: keep its words, but the warning
    # blocks still have to reach the user.
    _warnings = _doc_tool_summary(info, warnings_only=True)
    if _warnings:
        _chunk = "\n\n" + _warnings
        full_response = _fr + _chunk
        return full_response, _chunk
    return full_response, ""


def end_of_turn_report(
    full_response: str,
    tool_events: list,
    *,
    doc_info: Dict[str, Any],
    doc_text_before_tool: Optional[str],
    text_before_last_tool: Optional[str],
) -> Tuple[str, List[str]]:
    """Everything the end of a turn appends for the reader, in order.

    Returns ``(full_response, chunks)``; the caller yields each chunk (already
    SSE-framed). Must run after ``strip_tool_blocks``: a response that was only
    a tool fence is empty to the user, whatever it looked like mid-stream.
    """
    chunks: List[str] = []
    # Document closing line - the model-agnostic half of the split gate.
    # Without it a silent document turn was saved as a bare "Done.". The
    # finetune path already did this at its loop break, so full_response is
    # non-empty there.
    _preamble_only = _text_is_only_preamble(full_response, doc_text_before_tool)
    full_response, _doc_summary_chunk = _closing_doc_summary(
        full_response, doc_info, preamble_only=_preamble_only,
    )
    if _doc_summary_chunk:
        chunks.append(_doc_summary_chunk)
        logger.info(
            "[agent] synthesized document closing line "
            "(tool=%s calls=%s applied=%s skipped=%s stale=%s appended_to_preamble=%s)",
            doc_info.get("tool"), doc_info.get("calls"),
            doc_info.get("applied"), doc_info.get("skipped"),
            doc_info.get("stale_values"), _preamble_only,
        )

    # Non-document tools: the turn looked things up and then said nothing (or
    # only a promise written before the tools ran). The notice is appended so
    # the model keeps its own opening.
    _gather_preamble_only = _text_is_only_preamble(full_response, text_before_last_tool)
    if not full_response or _gather_preamble_only:
        _gathering_notice = _gathering_only_notice(tool_events)
        if _gathering_notice:
            if full_response.strip():
                _chunk_text = "\n\n" + _gathering_notice
                full_response = full_response.strip() + _chunk_text
            else:
                _chunk_text = _gathering_notice
                full_response = _gathering_notice
            chunks.append('data: ' + json.dumps({"delta": _chunk_text}) + '\n\n')
            logger.info(
                "[agent] turn gathered information but produced no answer "
                "(tools=%s preamble_only=%s)",
                [ev.get("tool") for ev in tool_events], _gather_preamble_only,
            )

    # A tool that CHANGED something outside a document, unreported. Successes
    # are reported only when the model stayed silent or never got past its
    # preamble; failures always. Snapshot the gate BEFORE appending - the
    # branches below mutate full_response, and recomputing would read our own
    # notice as the model's words.
    _model_reported = bool(full_response) and not _gather_preamble_only
    _side_effect_summary = _side_effect_tool_summary(
        tool_events, failures_only=_model_reported,
    )
    if _side_effect_summary:
        _chunk_text = ("\n\n" if full_response.strip() else "") + _side_effect_summary
        full_response = full_response.rstrip() + _chunk_text
        chunks.append('data: ' + json.dumps({"delta": _chunk_text}) + '\n\n')
        logger.info(
            "[agent] synthesized non-document tool report "
            "(tools=%s failures_only=%s)",
            [_resolved_tool_event_name(ev) for ev in tool_events], _model_reported,
        )

    # Zero-tool cases, which the guards above cannot reach. The payload-as-text
    # notice is checked first and suppresses the promise notice: both need zero
    # tools, but this one knows why nothing happened (the text often claims
    # success rather than trailing off).
    _payload_notice = _tool_payload_as_text_notice(full_response, tool_events)
    if _payload_notice:
        full_response = full_response.rstrip() + _payload_notice
        chunks.append('data: ' + json.dumps({"delta": _payload_notice}) + '\n\n')
        logger.info("[agent] turn emitted a tool payload as display text; no tool ran")

    _unstarted_notice = "" if _payload_notice else _unstarted_promise_notice(full_response, tool_events)
    if _unstarted_notice:
        _chunk_text = " " + _unstarted_notice
        full_response = full_response.rstrip() + _chunk_text
        chunks.append('data: ' + json.dumps({"delta": _chunk_text}) + '\n\n')
        logger.info("[agent] turn announced work, called no tools, and stopped")
    return full_response, chunks
