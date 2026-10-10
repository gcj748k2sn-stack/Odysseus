# Odysseus as a background service (macOS, launchd)

Runs the server without a Terminal window: it starts at login and restarts if
it crashes. The UI is then installed as a web app from the browser, so it gets
its own Dock icon and window.

| Agent | Runs | Log |
|---|---|---|
| `local.odysseus.chroma` | ChromaDB on 127.0.0.1:8100 | `logs/chroma-service.log` |
| `local.odysseus.apfel` | Apfel on :11435 (only if `apfel` is installed) | `logs/apfel-service.log` |
| `local.odysseus` | the app on 127.0.0.1:7860 | `logs/app-service.log`, app log as before in `data/logs/app.log` |

SearXNG has its own agent, `local.searxng` (see `searxng/`). Ollama runs under
`brew services`.

```bash
bash /Users/cedrik/odysseus/launchd/install.sh      # install or reload (idempotent)
launchctl list | grep local.odysseus                 # status: PID, last exit code
launchctl kickstart -k gui/$(id -u)/local.odysseus   # restart, e.g. after a merge
bash /Users/cedrik/odysseus/launchd/uninstall.sh    # back to ./start-macos.sh
```

- **Restart after pulling code.** On every start, `run.sh` reinstalls the
  packages if `requirements.txt` changed (the same hash file `start-macos.sh` uses).
- **`./start-macos.sh` still works.** While the agent is loaded it only opens the
  UI (`handoff.sh`). The old `Odysseus.app` already does that when the port answers.
- **Closing the window doesn't stop the server.** Stop it with `uninstall.sh`, or for
  this session only with `launchctl bootout gui/$(id -u)/local.odysseus`.
- Settings (`APP_PORT`, `APP_BIND`, `CHROMADB_*`) come from `.env`, as in
  `start-macos.sh`. After changing them, re-run `install.sh`.

## App window

- **Chrome:** open http://127.0.0.1:7860, then choose ⋮ → *Cast, save and share* →
  *Install page as app…*. The app appears in `~/Applications/Chrome Apps`, in
  Launchpad and in the Dock.
- **Safari:** open http://127.0.0.1:7860, then choose *File → Add to Dock*.

Both use `static/manifest.json` (name, icon, standalone display), which is already
in the repo.
