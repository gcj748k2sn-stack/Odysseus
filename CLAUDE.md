# Working rules for coding agents in this repo

Short and imperative on purpose. Every rule here was learned by getting it wrong,
most of them twice. The incident behind each one is in
[`notes/archive/CLAUDE-full-2026-10-06.md`](notes/archive/CLAUDE-full-2026-10-06.md);
read it when a rule seems arbitrary, not by default.

**Read [`notes/session-log.md`](notes/session-log.md) first.** It is what the last
sessions actually *did* (scope and state, not findings), and it is the one thing
no session can otherwise see. Then [`notes/todo.md`](notes/todo.md): the open
items, one row each; an item longer than a screen has its full record in
`notes/items/`.

**`notes/archive/` is history, never current state.** Verbatim snapshots,
append-only, not kept up to date. Do not cite anything there as a live finding
without re-checking it against the tree, `app.log` or `app.db`. Superseded prose
gets argued from as if it were live whatever banner sits above it, which is why
it lives out of the default read path.

## 0. This is a fork

The repo is a fork of `odysseus-dev/odysseus` and merges upstream `dev`
regularly (2026-10-06: 132 upstream commits, 25 files conflicted). Merge cost
grows with every fork line that sits inside an upstream file.

- **Put fork logic in fork modules and leave a call site in upstream code, not a
  body.** `stream_agent_loop` in `src/agent_loop.py` is upstream's most-changed
  function. Fork modules: `src/turn_report.py` (end-of-turn notices, closing
  summaries, document-tool accounting), `src/browser_gate.py`,
  `src/known_facts.py`, `src/document_fidelity.py`, `src/ui_notices.py`,
  `src/named_machines.py`, `src/access_log_filter.py`, `scripts/bench_*.py`.
- **Code comments say what and why, in a few lines.** Incident history (run
  ids, dates, measurements) belongs in `notes/`, not in code. Cite a notes entry
  by its title, never by item number.

## 1. Evidence

**Check the cheapest source first, and check the *writer* of the evidence, not
just the evidence.**

- **`data/logs/app.log*` before `data/app.db`.** The log has `[agent-timing]`
  lines per round and the provider's own error payload.
- **`app.log` is local time; `app.db` timestamps are naive UTC. Read the
  offset, never assume it** — 2 h under CEST, 1 h from the last Sunday in
  October. An empty log window is usually the wrong offset. (`_formatter` in
  `app.py` uses local time; `utcnow_naive()` in `core/database.py` is UTC;
  `last_accessed` uses `func.now()`, a third mechanism that agrees on SQLite.)
- **`app.log` rotates** (5 MB × 3, the `RotatingFileHandler` in `app.py`).
  Grep `app.log*` for coverage, but the glob is lexical — `app.log` comes first,
  so `| tail` shows the OLDEST matches. Sort by timestamp, or grep one file. The
  12–28 July evidence base is in a rotated file: copy rotated logs into the
  snapshot tarball with `app.db`.
- **Copy `app.db` before querying it, in the same bash call.** Each sandbox call
  is fresh, and `sqlite3.connect` silently creates a missing file — the
  resulting `no such table` reads like a schema change.
- **Nothing on disk says whether the app is running.** `data/app.db-journal`
  exists only during a write (journal mode `delete`): absent means nothing,
  stale reads as running. Use `lsof /Users/cedrik/odysseus/data/app.db` and read
  the mode column: `r` handles (macOS indexers; the agent sandbox's folder share
  under `Virtualization.framework` — `lsof -p <pid> | grep -c odysseus` tells a
  share from a client) cannot make a copy inconsistent; `w`/`u` can.
  `bird`/`CloudDocs`/`FileProvider` would be a different problem. The check
  that cannot be argued with: hash, copy, hash again, diff.
- **Set `DATABASE_URL=sqlite:///:memory:` before importing anything under
  `src/`.** `core/database.py` runs `init_db()` at import — migrations and
  `create_all` against whatever `DATABASE_URL` says, by default the live
  `data/app.db`. Verify with a hash of a copy taken beforehand, not
  `integrity_check`.
- **The sandbox can create files it cannot delete** — under `.git/`, `data/`,
  anywhere in the mount. Say what you left and where, with the finding.
- **Before blaming code for missing rows, read `task_runs.result`.** Event-
  triggered actions (Documents Tidy) name their own deletions there; `app.log`
  only says "completed". `select id,task_id,started_at,status,result from
  task_runs order by started_at desc limit 20`.
- **Orphaned child rows say nothing about an app delete** (`DocumentVersion`
  cascades), and both cascade halves are ORM/PRAGMA-dependent — the `sqlite3`
  CLI fires neither. Prepend `PRAGMA foreign_keys=ON;` to any hand-run delete.
- **`app.db` lags live activity** (rows land on `save_sessions()`), so the
  newest row is not necessarily the last turn.
- **A field is not the thing its name suggests; check when it started being
  written before reading its absence.** `command` is a first-line preview;
  `tool_events[].full_command` and `round_texts` exist only on rows after
  2026-07-28 (test `'full_command' in event`, not `.get()`); `full_command` on
  document tools is a rendered form, not the raw arguments; `input_tokens` is
  summed across rounds — use `request_context_tokens` for context fullness.
- **A replay that reconstructs its own input proves nothing.** Ask what the
  reconstruction assumed.
- **A turn that "produced nothing" may have answered in the reasoning channel.
  Read `thinking` before `content`.**
- **An absence in the log is evidence only if the thing could have been
  logged.** Check the call site and level: the root logger is INFO, so DEBUG
  never appears (`grep -c ' - DEBUG - ' data/logs/app.log`), and SSE frames are
  not logged at all.
- **A count of files is not a count of behaviours, and a tool call is not its
  result.** Read the callers and the `exit_code`. When a claim comes from a
  grep, name the grep so the next reader sees what it could not have seen.

## 2. Claims in the docs are unverified until you re-check them

`notes/todo.md`, `notes/items/` and `notes/resolvedissues.md` have been wrong
in repeating ways: "fixed" from one happy-path run; a mechanism from a symptom
string; a blocker that could not have helped; stale effort estimates; and
*Notes & constraints* entries that were false all along — that section is
re-read least, so trust it least.

- **Re-check line numbers, callers and field contents against the tree before
  building on them.** Say so when a filed claim is wrong: a correction is worth
  more than the finding it corrects.
- **Retractions are load-bearing.** Read the retraction before reopening a
  closed road, and check which layer it applies to.

## 3. Guards

- **A guard that only reports can ship on test evidence. A guard that makes the
  model act can destroy data** (a retry nudge once wiped a 6,186-character
  document). Tests for an acting guard must bound what it can do.
- **Check that a guard fails in the failing case before checking that it
  passes.**
- **A reproduction that deletes, empties or closes must name the throwaway
  object to use and the check that the safety mechanism is engaged** (e.g. type
  one character, confirm no `[doc-save]` line). An unverified precondition is
  not a precondition.
- **Measure a detector by mutating it, and write the mutation down with its
  score.** A score without its mutation cannot be re-derived.
- **Don't detect malformed output with a parser** — it filters out your own
  evidence. Match lexically.
- **Every checker that flags needs negative controls** ("this input must
  produce nothing"), and **validation against the whole recorded corpus**, not
  just its fixtures.

## 4. Tests

Policy: [`tests/TESTING_STANDARD.md`](tests/TESTING_STANDARD.md). Helpers:
[`tests/README.md`](tests/README.md).

- **Run with `./venv/bin/python -m pytest -n auto`** (pytest-xdist, about
  80 s on the M1). System `python3` lacks pinned dependencies. `--noconftest` drops fixtures, markers, the suite's own data
  dir and the in-memory database — don't use it.
- **A sandboxed agent cannot run the M1 venv** (a macOS tree). Report exactly
  which files ran with what, never a whole-suite number you did not produce, and
  hand the full run to the maintainer. On every sandboxed run set
  `DATABASE_URL=sqlite:///:memory:` and `PYTHONDONTWRITEBYTECODE=1`, and pass
  `-p no:cacheprovider`.
- **There is no JavaScript test harness.** `static/js/` ships on `node --check`
  and review: write "unverified" in the commit and the item, and name the one
  manual step that would confirm it.
- **Stub packages: point `__path__` at the real package, never `[]`**, and
  `monkeypatch.delitem(sys.modules, …)` before an import test, or the module
  cache can make it pass for the wrong reason. Five other test files still use
  `__path__ = []`; the inventory is pinned in `test_review_regressions.py`.
- **A fixture's location can be load-bearing.** Before moving one, run the
  function that confines it and see whether the new place satisfies it on its
  own (`$TMPDIR` and `/tmp` are already allowed roots).
  `test_chat_helpers.py` builds fixtures in the repo root on purpose.
- **`realpath` whatever you hand a roots/allowlist helper** — macOS `$TMPDIR`
  sits under `/var` → `/private/var`.
- **`ignore_errors=True` hides a failed cleanup.** A cleanup that cannot fail
  cannot tell you it failed.
- **The suite has its own empty data dir** (`tests/conftest.py`, since
  2026-10-06). Build paths from the constants (`DEEP_RESEARCH_DIR`,
  `SKILLS_DIR`, …), never from `"data/…"` — that is the way back into the live
  `data/`.
- **`area_*` markers key off filenames, not subject matter** — `-m
  area_security` is not a security gate.
- **Wiring tests (`test_*_wiring.py`) are the deliberate exception to
  behaviour-first**: they pin structure ("findings never reach a model-facing
  path"). Keep the exception narrow and say why in the docstring.

## 5. Writing in the docs

- **Record the scope a fix was verified at**, not just the outcome — *Verified*
  is tracked separately from *Fixed*.
- **Numbers in prose are claims with no test.** Collect counts mechanically, and
  say when you predicted rather than measured.
- **Cite entries by title, not by number.** Before renumbering anything, grep
  `--include=*.py --include=*.js` too.
- **Closing an item:** move the conclusion to `resolvedissues.md` (keep
  retractions, recurring traps, ground truth and verification scope), move its
  row to the closed index there, and move its `notes/items/` file to
  `notes/archive/`. Mechanism walkthroughs are re-derivable from `git show`.
- **Delete superseded prose instead of bannering it**, or move it to the
  archive.
- **Keep the default read path small.** A session-log entry is a few lines; an
  item longer than a screen gets its own file in `notes/items/`; session-log
  entries older than the last working day move to `notes/archive/`.

## 6. Git

- **An agent in the Linux sandbox must not run git, except commands that take
  no index lock** (`git log`, `git show`, `git diff <commit> <commit>`,
  `git archive`) — check before assuming a command is read-only; `git status`
  takes the lock. The mount allows creating `.git/index.lock` but not deleting
  it, and a leftover lock blocks every git operation silently. Hand every
  `add`/`commit`/`stash` to the maintainer with exact commands.
- **`index.lock` is a mutex, not data** — deleting it never touches history.
  Check `ls .git/index.lock` before believing git is broken.
- **Fetch before trusting ahead/behind.**
- **Ignoring a file is not protecting it.** `data/app.db` is gitignored, and
  `git clean -fdx` would take it. The snapshot tarball protects the evidence.
- **A green suite tests the tree, not the commit.** Before writing "done" on
  anything that added a file, run `git archive HEAD | tar -x -C /tmp/x && diff
  -rq /tmp/x .` — it names every file in no commit, takes no lock, and avoids
  the CRLF trap of `git show HEAD:<file>` on the `*.ps1`/`*.bat` scripts.
- **Marking an item done and handing back the commit commands are one
  action.** The message that says "done" contains the commands to commit it.
- Conventional Commits, per [`CONTRIBUTING.md`](CONTRIBUTING.md).

## 7. Handing steps back to the maintainer

- **Every step the maintainer runs gets the full command, ready to paste**, with
  this machine's absolute paths (`/Users/cedrik/odysseus`,
  `~/odysseus-snapshots`), in order. This matters most for the steps an agent
  cannot run itself: git, and pytest on the M1.
- **Include the verification command**, not just the action (`shasum -c` after a
  `tar`).
- **Say which directory a command assumes**, or use absolute paths.
- **macOS, not Linux:** `shasum -a 256`, not `sha256sum`; BSD `sed -i ''`, not
  GNU `sed -i`.
