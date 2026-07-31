# Working rules for coding agents in this repo

Short and imperative on purpose. Everything here was learned by getting it wrong
at least once, and most of it twice.

**The structural problem this file exists for:** every session that edits
`docs/todo.md` is a different session, and none of them can see the others. The
docs record findings; this file records *how to work*, so each session doesn't
re-derive it.

**Read [`docs/session-log.md`](docs/session-log.md) first, before anything
else.** It's a short, dated, reverse-chronological log of what the *previous
session actually did* — scope and state changes, not findings (those are
`todo.md`/`resolvedissues.md`). It's the one thing no session can otherwise see.

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
- **Before blaming code for missing rows, check whether a SCHEDULED TASK ate
  them — `task_runs.result` names its own damage.** Item 31 filed *"closing a
  document tab can hard-DELETE it"* and cited **70 rows → 62** as the evidence.
  Both numbers came from a single row: `task_runs.ad505282`, *"Removed 8 of 70
  … (+8 duplicate copies) · 62 kept"* — the Documents Tidy action, firing on
  every fifth `document_created`. `app.log` says only *"Task 'Documents Tidy'
  completed (run ad505282)"*; **the result string lives in the database, so the
  log alone makes an automatic deletion look like an unexplained one.** These
  actions are event-triggered, not scheduled, so nothing in the record suggests
  a clock to correlate against. `select id,task_id,started_at,status,result
  from task_runs order by started_at desc limit 20` is the ten-second check.
- **Do not test for hard deletes by looking for orphaned child rows.**
  `DocumentVersion` is `cascade="all, delete-orphan"` with
  `ondelete="CASCADE"`, so a hard-deleted document takes its versions with it
  and the orphan count is **zero either way**. That sweep was run, came back
  clean, and proved nothing. **Check the cascade before believing an
  absence** — same shape as the DEBUG-level greps above.
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
  - **Check `'full_command' in event`, not `event.get('full_command')`.** A
    sweep for "document calls that arrived empty" returned **9**; eight of them
    are pre-2026-07-28 rows where the key does not exist at all, so their
    emptiness is item 10's recording gap, not an empty call. **n was 1, not 9**
    — and a filed claim citing a 2026-07-18 run as evidence of what a call
    carried cannot be true, because nothing recorded it then.
- **If a replay reconstructs its own input, it proves nothing.** Rebuilding
  `thinking + content` and re-splitting it reproduces the stored split by
  construction. Ask what the reconstruction assumed before believing the match.
- **A turn that "produced nothing" may have produced everything, on the wrong
  channel. Read `thinking` before believing `content`.** A round logging
  `text_chars=0 tool_calls=0` after 109 seconds held 3,892 characters of
  finished, headed, user-facing report in `thinking` — and the guard reported
  *"stopped without producing an answer"*, which was true about tools and false
  about the answer. **`round_texts` does not separate this from a genuine
  stall** (it is `''` either way, because nothing arrived as content);
  `thinking` vs `content` does. docs/todo.md items 8 and 23.
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
- A *settled constraint* has been false since before the items resting on it
  were filed. "Local models get no tool schemas at all" was the stated reason
  item 8's active half had to be a text nudge — and that nudge destroyed a
  document. **The `Notes & constraints` section is not more trustworthy than
  the items; it is less, because nothing re-reads it.**

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
- **A REPRODUCTION that makes the maintainer act can destroy data, and it is
  handed over with none of the caution an acting guard gets.** The item 31(b)
  procedure — *"select all, delete, then close the tab before the save lands"* —
  emptied **four documents** on 2026-07-31, one of them 18,237 characters,
  because the network throttle that was the entire safety mechanism silently
  did not take. They turned out to be disposable test fixtures and all four
  were recoverable from `document_versions` anyway — **but nothing in the
  procedure knew either of those things.** That is luck twice over, not design.
  **Any repro that deletes, empties or
  closes must say which throwaway object to do it on, and must name the check
  that the safety mechanism is actually engaged** — here, *type one character
  and confirm no `[doc-save]` line appears*. **An unverified precondition is
  not a precondition.**
- **Measure a detector by MUTATING it, not by running it.** Running the shipped
  version over the corpus tells you it fires; breaking one branch and re-running
  tells you which branch is doing the work. The payload-as-text guard: the
  unterminated-fence branch is **not** load-bearing (a closed-fence-only variant
  still scores 3 of 3), and the lexical check is, because the payload it exists
  to catch is malformed JSON. **Both facts came from mutation; both were guessed
  wrong beforehand and one of the guesses was already written into the
  docstring.**
- **Write the MUTATION down, not just its score.** The line above used to read
  *"a `json.loads` variant catches 1 of 3"*. Re-checked 2026-07-29: the shipped
  detector scores 3 of 3 and the closed-fence mutation reproduces exactly, but
  **the `1 of 3` cannot be reproduced** — no record says which parsing variant
  was run, and a plausible reconstruction scores 2 of 3. The claim is neither
  confirmed nor refuted; it is **unfalsifiable as filed**, which is the worse
  outcome. A score without its mutation is a number nobody can re-derive. *(The
  same figure appeared as "1 of the 2 recorded instances" in the docstring, on a
  corpus that held 3 — see `_fenced_regions`.)*
- **A parser is the wrong tool for detecting malformed output.** The thing you
  are looking for is malformed by definition, so `json.loads` filters out your
  own evidence. Match lexically.
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
- **There is NO JavaScript test harness.** `package.json` has one devDependency
  and no runner, so anything under `static/js/` ships on `node --check` and
  review alone. **Say "unverified" in the commit and in the item**, and name the
  one manual step that would confirm it. Half of what the UI does — session
  selection, the document panel, what `active_doc_id` the frontend sends — is
  only observable from `app.log` afterwards.
- **A stub package with `__path__ = []` encodes today's import list of the code
  it exercises.** `test_review_regressions.py` replaced `core` that way and six
  tests died with `ModuleNotFoundError: No module named 'core.log_safety'` — a
  file that exists, is committed, and imports fine everywhere else. Point
  `__path__` at the real package instead; `sys.modules` still wins for the
  submodules you actually stub. **Five other test files still do this**; the
  inventory is pinned in `test_review_regressions.py`.
- **`sys.modules` is consulted before `__path__`, which can make an import test
  pass for the wrong reason.** The first negative control written for the fix
  above passed with the bug still in place, because the module was already
  cached from an earlier import. `monkeypatch.delitem(sys.modules, ...)` is what
  turned it into a test. **Revert the fix and watch it fail before believing it.**
- **A test fixture's LOCATION can be load-bearing, and moving it can make the
  test vacuous.** `test_chat_helpers.py` builds fixtures in the repo root, which
  looks like litter and isn't: `DATA_DIR` is `<repo>/data`, so a repo-root path
  is outside every entry in `_tool_path_roots()`, and that is the only reason
  the test's `tool_path_extra_roots` patch discriminates. Under `tmp_path` —
  which lives in `$TMPDIR` or `/tmp`, both already on the allowlist — every
  assertion still passes and the patch stops mattering. **`test_extra_roots_opt_in`
  in `test_tool_path_confinement.py` has that defect today** (todo.md item 25).
  **Before moving a fixture, run the function it is confined by and see whether
  the new location satisfies it on its own.** Reading the test cannot show this.
- **If you replace a roots/allowlist helper in a test, `os.path.realpath` what
  you hand it.** The real `_tool_path_roots()` normalises its own inputs; a
  `lambda: [str(tmp_path)]` skips that, and on macOS `$TMPDIR` is under the
  `/var` → `/private/var` symlink — so the test fails on macOS and passes on
  Linux. That is the item 19 class, re-manufactured by the fix for a different bug.
- **`ignore_errors=True` is a silent failure by design.** `shutil.rmtree(root,
  ignore_errors=True)` in a `finally` reads as "cleanup is handled" and means
  "cleanup may or may not have happened, and you will not be told". A sandboxed
  run cannot delete under the mount, so four fixture directories accumulated in
  the repo root, unignored, showing as untracked in every `git status` — the one
  check item 5 depends on. **A cleanup that cannot fail cannot tell you it failed.**
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
- **A green suite says nothing about what is committed — it tests the tree, not
  the commit.** On 2026-07-29 `src/agent_loop.py` was committed while
  `src/known_facts.py`, which it imports at module top, was untracked: `HEAD`
  could not import, the branch was 19 commits ahead of origin, and every test
  had always run in a tree where the file happened to exist. **Before writing
  "fixed" on anything that ADDED a file, run `git status`** — new modules,
  fixtures and test files are untracked by default. The mechanical check is a
  sweep of every first-party `from (src|routes|core|services)... import`
  against the files on disk; it takes seconds and it is what found this.
  - ⚠️ **It recurred on 2026-07-29, hours after being closed from a clean
    clone.** The whole of the payload-as-text work — the two detector functions
    in `src/agent_loop.py`, the retry-text change in `document_tools.py`, and
    `tests/test_tool_payload_as_text.py` — sat uncommitted while `docs/todo.md`
    recorded it as *"✅ built — tests (14)"*. **Milder than the `known_facts.py`
    instance** (nothing untracked is imported, so `HEAD` still runs) and the
    same failure: **the drift starts the moment an item is marked done.** The
    untracked file is a *test*, which `git add -u` does not pick up and
    `git add .` does.
- **Marking an item done and handing back the commit command are ONE action,
  not two.** This is what closed the uncommitted-work item on 2026-07-31, after
  four recurrences and two reminder-shaped rules that did not stop it. Every
  recurrence began in the message that wrote *"✅ fixed"* and did not write a
  `git commit` line. The agent cannot commit — the bullet at the top of this
  section forbids it — so **the handback is the only enforceable half**: full
  commands, real absolute paths, in the same message as the claim. The check
  afterwards is mechanical and needs no judgement: *did the message that said
  "done" contain the commands to commit it?*
  - **A periodic reminder is the wrong shape and has already failed twice.**
    The failure has a trigger, not a cadence — it starts when an item is marked
    done — so the rule has to attach to that moment. "Commit regularly" does
    not.
  - **Before writing "done" anywhere, run the tree diff below** — `git archive
    HEAD | tar -x -C /tmp/x` then `diff -rq /tmp/x .`. It takes no index lock,
    so a sandboxed agent may run it, and it names every first-party file that
    is in no commit. **This is the check, not `git status`.**
- **A sandboxed agent CAN answer "what is uncommitted" — with `git archive`, not
  with blob diffs.** `git archive HEAD | tar -x -C /tmp/x` then `diff -rq /tmp/x .`
  reads a tree, takes no index lock, and is what found the recurrence above.
  **It also dodges the CRLF trap** that makes `git show HEAD:<file>` report the
  three `*.ps1`/`*.bat` scripts as modified when they are clean — `git archive`
  applies the same `eol` attributes the working tree has. It cannot replace
  `git status` (it says nothing about the index, or about ignored files), but
  "which tracked files differ from HEAD, and which files on disk are in no
  commit" is answerable without touching git's write paths.
- Conventional Commits, per [`CONTRIBUTING.md`](CONTRIBUTING.md).

## 7. Handing steps back to the maintainer

**Any step the maintainer is expected to run gets the full command, ready to
paste.** Not a description of the command, not a fragment, not "snapshot the
database first" — the actual line, with the real absolute paths of this machine
(`/Users/cedrik/odysseus`, `~/odysseus-snapshots`), in the order it must run.

- **This applies hardest to the steps an agent cannot run itself.** Everything
  in §6 is handed over by definition, and so is any `pytest` run — `./venv/bin/`
  is a macOS tree and a sandboxed agent cannot execute it. Those are exactly the
  steps most likely to be described instead of written out, because the agent
  never had to make them work.
- **Include the verification command, not just the action.** A `tar` line
  without the `shasum -c` that proves the archive matches is half a step, and
  this repo has a whole section on why "it ran" is not "it worked".
- **Say which directory the command assumes**, or use absolute paths. Each
  sandbox `bash` call starts fresh with no `cd` carried over, so a relative
  command that worked in the agent's transcript is not reproducible by hand.
- **macOS, not Linux:** `shasum -a 256`, not `sha256sum`; BSD `sed -i ''`, not
  GNU `sed -i`. A command lifted from a sandbox run is a Linux command until
  checked.
