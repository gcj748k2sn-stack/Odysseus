# Working rules for coding agents in this repo

Short and imperative on purpose. Everything here was learned by getting it wrong
at least once, and most of it twice.

**The structural problem this file exists for:** every session that edits
`docs/todo.md` is a different session, and none of them can see the others. The
docs record findings; this file records *how to work*, so each session doesn't
re-derive it.

---

## 1. Evidence

**Check the cheapest source first, and check the *writer* of the evidence, not
just the evidence.**

- **`data/logs/app.log` before `data/app.db`.** The log carries
  `[agent-timing] round_start / first_event / first_visible_token /
  round_stream_done` per round, and `stream_error` with the provider's own
  payload. A whole session was once spent inferring a "throughput cliff" from
  database columns; the answer was a `504 Read timeout` sitting in the log,
  found in one grep.
- **`app.log` is local CEST. `app.db` timestamps are naive UTC.** Two hours. An
  empty log window is usually the wrong two hours, not an absent event.
- **`app.log` ROTATES — always grep `data/logs/app.log*`, never `app.log`.**
  `RotatingFileHandler(maxBytes=5MB, backupCount=3)` at `app.py:107`. It rotated
  for the first time on 2026-07-28 at 23:21:34, and within the hour a grep of
  `app.log` alone produced a confident causal finding about turns whose log
  lines had moved to `app.log.1` forty minutes earlier. **The whole 12–28 July
  evidence base these docs reason about is now in `app.log.1`**, and three more
  rotations delete it — copy it into the snapshot tarball alongside `app.db`.
- **Copy `app.db` before querying it.** The running app holds it;
  `data/app.db-journal` on disk is how you tell it's running. A direct read can
  fail with `disk I/O error`, and importing app modules runs migrations against
  the real database.
- **Set `DATABASE_URL=sqlite:///:memory:` before importing anything under
  `src/`.** This is what the line above costs when you forget it: an import
  from `src.agent_loop` ran five migrations against the live `data/app.db`,
  failed each with `disk I/O error`, and left a hot `data/app.db-journal`
  behind — which then read as *the app is running* to the next person to `ls`.
  Nothing was lost (the app rolled the journal back on next open; row counts,
  ids and every message body compared identical to a pre-import copy), and it
  was luck, not design. `tests/conftest.py` already does this; ad-hoc probes
  must too. **Verify with a hash of a copy taken beforehand, not with
  `integrity_check`** — an intact database that quietly lost a row passes that.
- **The sandbox can create files it cannot delete, and this is not limited to
  `.git/`.** Same mount rule applies under `data/`: the stale journal above
  could not be removed from the sandbox at all. Anything a sandboxed run
  leaves behind is the maintainer's to clean up, so say what was left and
  where, in the same breath as the finding.
- **`app.db` lags live activity.** Rows are written on `save_sessions()`, so
  "the newest row" is not "the last turn". A query can miss the run you are
  looking for and look perfectly healthy doing it.
- **A metadata field is not the thing it appears to name.** `command` is a
  first-line preview, not the argument. `tool_events[].full_command` and
  `round_texts` only exist on rows written after 2026-07-28. Check when a field
  started being written before concluding anything from its absence.
  - **`input_tokens` is the SUM ACROSS ROUNDS, not the request size.** Use
    `request_context_tokens` for "how full was the context". A turn showing
    `input_tokens: 91,212` against a 32,768 window was one keystroke from being
    filed as a context-overflow bug; its real per-request peak was 17,712 (54 %).
  - **`full_command` on a document tool is a RENDERED form**, title and content
    joined — not the raw JSON arguments. All 35 recorded values contain no
    `"title"` key, so wire-level questions (key order, argument shape) cannot be
    answered from it.
- **If a replay reconstructs its own input, it proves nothing.** Rebuilding
  `thinking + content` and re-splitting it reproduces the stored split by
  construction. Ask what the reconstruction assumed before believing the match.
- **An absence in the log is only evidence if the thing could have been
  logged.** Check the emitting call site and the level before concluding
  anything from a zero count. Three items were built on one grep this way:
  *"zero `tool_call_delta` in 35,744 lines"* (emitted at `logger.debug`; the
  root logger is INFO at `app.py:88` and `app.log` has **no** DEBUG lines at
  all) and *"zero `doc_stream_open`/`doc_stream_delta`"* (SSE frames yielded to
  the browser — no logger call exists on those paths). Both greps measured the
  logging configuration. `grep -c ' - DEBUG - ' data/logs/app.log` is the
  ten-second check that would have caught the first.
- **A count of files is not a count of behaviours.** "Four independent
  `_PRIVATE_NETWORKS` copies" came from `grep -l` and survived three sessions
  as a security finding; reading the callers showed two are endpoint
  classifiers and the two real guards agree. Same shape as reading a tool
  *sequence* instead of a tool *result* — `write_file` in a turn's
  `tool_events` looked like a file written, and `exit_code=1` said it was
  refused. **When a claim comes from a grep, name the grep, so the next reader
  can see what it could not have seen.**

## 2. Claims in the docs are unverified until you re-check them

`docs/todo.md` and `docs/resolvedissues.md` are the working record, and they
have been wrong in specific, repeating ways:

- "Fixed" has twice been recorded from a single happy-path run.
- A mechanism has twice been recorded from a symptom string.
- An item has recorded itself blocked on a dependency that could not have helped.
- Effort estimates go stale because nobody re-reads the code after filing.

So: **re-check line numbers, callers and field contents against the tree before
building on them.** Say so when a filed claim turns out to be wrong — a
correction is worth more than the finding it corrects.

**Retractions are load-bearing.** Three re-investigations have been stopped by
one. Before re-opening a closed road, read the retraction *and* check which
layer it applies to — the reasoning-parser retraction is about `llm_core.py`
during the stream, and did not cover a save-path regex in
`routes/chat_helpers.py`. Both were true at once.

## 3. Guards

- **A guard that only reports can ship on test evidence. A guard that makes the
  model act can destroy data.** A retry nudge telling an idle model to "finish
  the job NOW" wiped a 6186-character document. Tests for an acting guard must
  bound what it can do, not merely assert it exists.
- **A guard that passes in the failing case is not a guard.** Check it fails
  before you check it passes.
- **Negative controls are mandatory for anything that flags.** A checker with
  only positive cases can be a function that always fires and still look like it
  works. The document-fidelity and known-facts checkers each have a "this input
  must produce nothing" test, and both caught real false positives.
- **Validate a new checker against the whole recorded corpus, not just its
  fixtures.** Three fixtures passed while five false-positive classes were live;
  sweeping all 20 recorded documents found them.

## 4. Tests

Policy lives in [`tests/TESTING_STANDARD.md`](tests/TESTING_STANDARD.md) and
helper mechanics in [`tests/README.md`](tests/README.md). Read those. Additions:

- **Run with `./venv/bin/python -m pytest`.** The system `python3` lacks pinned
  dependencies and produces import errors that look like failures and are not.
  `--noconftest` has the same effect: it skips fixtures and marker registration,
  so unrelated tests fail for environmental reasons and a real failure is easy
  to miss in the noise.
- **An agent in a Linux sandbox cannot follow the rule above.** `venv/` is a
  macOS/homebrew tree and its interpreter is a broken symlink from anywhere
  else, so a sandboxed run is necessarily partial. **Say so.** Report which
  files were run and with what, never a whole-suite number you did not produce,
  and hand the full-suite run back to the maintainer on the M1.
- **Two pre-existing failures** in `test_document_put_version_conflict.py` —
  they patch a closure. Don't delete them; they cover a real CAS race.
- **The `area_*` markers key off filenames, not subject matter.** `-m
  area_security` is not a security gate: `test_shell_routes.py` lands in
  `area_routes`.
- **The wiring tests are a deliberate exception to the behavioral-first rule.**
  `test_*_wiring.py` assert on source text and AST because the property being
  pinned *is* structural — "these findings reach no model-facing path". Keep the
  exception narrow and say why in the file's docstring.

## 5. Writing in the docs

- **Record the scope a fix was verified at, not just the outcome.** `todo.md`
  tracks *Verified* separately from *Fixed* for this reason. "Verified live" on
  a turn that ran three tools does not cover a turn that ran none.
- **Numbers in prose are claims with no test.** "44 files, staged" described a
  state four days gone. Collect counts mechanically and say when you predicted
  rather than measured.
- **Cite entries by title, not by number.** Cross-file numeric references have
  no integrity check and read plausibly while pointing at the wrong thing. Four
  have rotted, all one-directional. Before renumbering, grep
  `--include=*.py --include=*.js` for `todo.md` too — source comments are
  cross-references and there are more of them than there are in the docs.
- **Closing an item means moving the conclusion to `resolvedissues.md` and
  cutting the narrative, not appending to it.** Keep retractions, recurring
  traps, ground truth, and verification scope. Drop mechanism walkthroughs —
  they are re-derivable from `git show`.
- **Prose that reads like a live finding will be treated as one, whatever
  banner sits above it.** A superseded document was argued from by a later agent
  who had just read the banner saying it was wrong. Delete the prose.

## 6. Git

- **An agent in the Linux sandbox must not run git at all.** The mount allows
  creating files under `.git/` but not deleting them, so *any* command that
  takes the index lock — including read-only-looking ones like `git status` —
  leaves a zero-byte `.git/index.lock` behind that it cannot release. That is
  almost certainly where the mystery lock in this repo came from. Inspect with
  `ls`, `cat .git/HEAD`, `stat`; hand every `add`/`commit`/`stash` to the
  maintainer with the exact commands. `git log`/`git show` are safe only
  because they take no lock — check before assuming a command is read-only.
- **`index.lock` is a mutex, not data.** Deleting it never touches
  `.git/index`, and `.git/index` is not history either. Say so before someone
  panics.
- **Check `ls .git/index.lock` before believing git is broken.** A zero-byte
  lock blocks every operation silently; one instance ran 13 hours and is the
  likely reason two weeks went uncommitted.
- **`git status` can report a stale `origin/dev`.** Fetch before concluding
  anything about ahead/behind.
- **Ignoring a file is not protecting it.** `data/app.db` is gitignored and
  holds every run the docs reason about; `git clean -fdx` would take it. The
  snapshot tarball is what protects the evidence base.
- Conventional Commits, per [`CONTRIBUTING.md`](CONTRIBUTING.md).
