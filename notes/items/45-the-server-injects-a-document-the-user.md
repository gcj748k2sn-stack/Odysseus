# 45. The server injects a document the user never named, and closing the editor does not stop it

Open item, moved here from `notes/todo.md` on 2026-10-07 so the dashboard stays short. Its row in the [todo.md](../todo.md) index carries the current status; this file is the full record.

---

- 🔴 **Seen live 2026-10-05 23:31** (session `cdb89980`): `[doc-inject] active_doc_id from frontend: 68647d12…` → *"cross-session active_doc_id 68647d12… (was session 8d72d72f…, now cdb89980…) — accepting and rebinding"* → injected *"Pink Oyster Mushroom Growth Phases - Pleurotus djamor"* (8,579 chars) into a chat that had never opened it. The page still had that document marked active from another chat, and the server **rebinds** instead of refusing. The later 00:29 turn in the same chat logged no injection, so it is per-request page state, not a stored binding. **Filed in its own right as item 62** (same event, mechanism and fix there).
**Found 2026-08-01 by the maintainer noticing a chat "had access to" a document that was neither added manually nor shown in the workspace.** It is real, it is by design, and the design is not visible from the UI.

**`routes/chat_routes.py`** — when the frontend sends no active document, three fallbacks run in order *(grep `[doc-inject]`, do not trust line numbers)*:

1. the newest active **email draft** in this session;
2. **`found by session fallback`** — the newest active document with `session_id == session`, `order_by(updated_at.desc()).first()`;
3. **`found by in-memory active id`** — whatever the tool layer last created or edited, accepted if `not cand.session_id or cand.session_id == session`.

**Measured across `app.log`:** the frontend sends `active_doc_id=''` on **344 of 445** turns, so a fallback is the *normal* path, not an edge case. Outcomes on the 121 turns that reached the decision: **83 by ID, 17 session fallback, 1 in-memory, 21 none.**

- 🔴 **This corrects a precondition recorded under item 2a.** That item says *"close the open document in the editor first"* to stop the model reasoning about a document it was handed. **Closing the editor does not stop it** — fallback (2) keys on `session_id`, not on what the editor is showing, so the newest document in the chat is injected anyway. **The instruction as written cannot be followed**, and fd0f9ba0's failure (asked three times, got nothing, because the model reasoned a document already existed) is explained by the fallback rather than by the editor.
- ⚠️ **Fallback (3) accepts `session_id IS NULL`, so it can inject a document belonging to no session into ANY chat.** That is the same population as the 11 orphaned rows recorded on 07-30 — reciprocal with #34, which produces session-less documents on the client side.
- ⚠️ **Not established: whether this ever crosses into a genuinely NEW chat.** Fallbacks (1) and (2) filter on `session_id == session`, so a fresh session should match nothing; (3) is the only route in. **The discriminating run is a brand-new chat with no message sent, then one question that would reveal a document** — and it has not been done.
  - ✅ **Answered 2026-10-05 23:38 — yes, through the explicit-id path:** New Chat leaves the previous chat's document current, the first message sends its id, and the server moves the document into the new chat. Filed as item 62 (#45↔#62).
- **Not obviously a defect.** The fallback exists so the agent can see the document it just wrote when the client fails to name it. **What is wrong is that it is unobservable from the UI**: the user sees no open document and the model sees one. A one-line notice in the closing summary would close the gap without changing behaviour — report-only, the class that ships on test evidence.
