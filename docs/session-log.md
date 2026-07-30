# Session log

Brief, dated summaries of what each session *did* — not findings (those live in
[todo.md](todo.md) and [resolvedissues.md](resolvedissues.md)), just scope and
state changes, so the next session isn't starting cold. Newest first. Keep each
entry to a few lines — if it needs more, the detail belongs in `todo.md` or
`resolvedissues.md` and this should just link to it.

---

## 2026-07-30 — afternoon session

- Committed the previous session's docs (`add7e328`) — `docs/session-log.md` was untracked and `CLAUDE.md` pointed at it, so a clean clone had a broken mandatory-reading link. **Item 5's fourth recurrence, closed.** Snapshot taken first: `~/odysseus-snapshots/odysseus-evidence-2026-07-30.tar.gz`, 1,448,264 bytes, three `OK` against pre-copy hashes.
- Added **`CLAUDE.md` §7** — hand steps back to the maintainer as full paste-ready commands with this machine's absolute paths, the verification command alongside the action, and macOS tooling (`shasum -a 256`, BSD `sed`).
- **Ran item 20's five-run protocol — effectively finished, and it points the opposite way from the filed baseline.** Nine sessions, all with the identical prompt and `[doc-inject] found by ID`: **6 of 6 uncontaminated runs created the document** (duplicate rule), **6/6 clean titles**, **0/6 wasted `manage_documents`**. The one refusal is the run whose document had been overwritten a second earlier. The *"1 of 4"* first reading is un-derivable as filed — see item 20.
- **Filed item 30: switching chats writes the editor buffer into the other chat's document.** An AI document was destroyed and a second chat's clone overwritten. Proven by hash, then **reproduced live** at 13:32:45 once `[doc-put]` instrumentation was added to `routes/document_routes.py`. A first fix attempt (buffer stamping in `document.js`) **did not hold** — read item 30 before touching it, including the three theories it has already killed.
- Two 9b data points fell out in passing: rounds of **813.3 s** and **433.1 s** both completed at `timeout=900`, where the old 300 s cap would have killed them. Also one round of **433.1 s that produced nothing and saved no assistant row at all**, and a turn opening at `request_context_tokens=40,857` against a 32,768 window.
- ⚠️ **Uncommitted on purpose at session end:** `routes/document_routes.py` (the `[doc-put]` log), `static/js/document.js` (the attempted fix + its logging), `docs/todo.md`. The fix is **unverified and known not to work**; decide commit-vs-revert before building on it.

## 2026-07-30

- Verified the `gcj748k2sn-stack/Odysseus` push: local `dev` HEAD (`5c896fd`) matches `origin/dev` exactly (a commit-SHA match proves the whole tree is identical, not just the tip). Repo has since been made public.
- Reviewed dependabot PR #1 (python: httpcore, pydantic-settings, `mcp` → 2.0.0 major, markitdown) and PR #2 (10 GitHub Actions SHA bumps). Flagged `mcp` 2.0.0 as needing a real test before merge, not just green CI — breaking changes include `FastMCP` → `MCPServer`, a new `Client` API, and removed `MCP_*` env vars.
- Set up an Obsidian vault at `docs/` to browse `CLAUDE.md` / `todo.md` / `resolvedissues.md` / `qwensetup.md` as a linked graph. This repo's `docs/` now also contains symlinks: `docs/CLAUDE.md`, `docs/CONTRIBUTING.md`, `docs/SECURITY.md` → their real root files, and `docs/tests/README.md` / `docs/tests/TESTING_STANDARD.md` → the real `tests/` files. All of them plus `.obsidian/` are gitignored — a plain-file grep across `docs/**` will otherwise double-count these.
- Root cause worth remembering: symlinking a single file into the vault carries its content but not its folder context, so any relative link inside it to a sibling (e.g. `tests/README.md` ↔ `TESTING_STANDARD.md`, or `CONTRIBUTING.md` → `SECURITY.md`) breaks unless that sibling is *also* symlinked at a matching relative path. Obsidian auto-creates an empty stub note on an unresolved link click, which looks identical to a real connected node in graph view — verify by opening the file, not by the graph shape.
- Fixed a real, non-Obsidian bug found in passing: `docs/setup.md`'s link to `email-outlook.md` had a redundant `docs/` prefix, broken for anyone reading it from inside `docs/` (not just from GitHub's repo-root rendering context).
- `docs/SECURITY.md` symlink confirmed resolving with real content, same check as the others. All five vault-bridging symlinks (`CLAUDE.md`, `CONTRIBUTING.md`, `SECURITY.md`, `tests/README.md`, `tests/TESTING_STANDARD.md`) verified working, nothing left empty. No open items from this session.
