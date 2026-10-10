#!/usr/bin/env bash
# Install Odysseus as launchd user agents: the server starts at login, restarts
# if it crashes, and no longer needs a Terminal window.
#
#   local.odysseus.chroma   ChromaDB          (always)
#   local.odysseus.apfel    Apfel on :11435   (only if apfel is installed)
#   local.odysseus          the web app       (always)
#
# Idempotent: re-run after editing a plist or run.sh. Undo with uninstall.sh.
set -euo pipefail
trap 'echo "✗ install.sh stopped unexpectedly at line $LINENO"' ERR

REPO="/Users/cedrik/odysseus"
DIR="$REPO/launchd"
LA="$HOME/Library/LaunchAgents"
DOMAIN="gui/$(id -u)"
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:$PATH"
fail() { echo "✗ $*"; exit 1; }

# Port and bind come from .env, as in run.sh.
# (grep exits 1 when the key is absent; under pipefail that would end the script.)
envval() { { grep -E "^[[:space:]]*$1=" "$REPO/.env" 2>/dev/null || true; } | tail -1 | cut -d= -f2- | sed 's/#.*//; s/[[:space:]]//g'; }
PORT="$(envval APP_PORT)"; PORT="${PORT:-7860}"
CHROMA_PORT="$(envval CHROMADB_PORT)"; CHROMA_PORT="${CHROMA_PORT:-8100}"
URL="http://127.0.0.1:$PORT"

# --- 0. Preconditions -------------------------------------------------------
[ -x "$REPO/venv/bin/python3" ] || fail "venv missing - run ./start-macos.sh once first"
"$REPO/venv/bin/python3" -c 'import uvicorn, chromadb' 2>/dev/null \
    || fail "uvicorn/chromadb don't import in the venv - run ./start-macos.sh once first"
[ -f "$REPO/data/app.db" ] || fail "no data/app.db - run ./start-macos.sh once first"

AGENTS="local.odysseus.chroma"
if command -v apfel >/dev/null 2>&1; then
    AGENTS="$AGENTS local.odysseus.apfel"
else
    echo "▶ apfel not found - skipping its agent"
fi
AGENTS="$AGENTS local.odysseus"
for a in $AGENTS; do
    plutil -lint "$DIR/$a.plist" >/dev/null || fail "$a.plist is malformed"
done
echo "✓ preconditions OK"

# --- 1. Stop whatever runs now ----------------------------------------------
# Earlier agents (re-run), then manual instances: start-macos.sh in a Terminal
# tab, its nohup'd ChromaDB/Apfel, or a server left behind by Odysseus.app.
for a in local.odysseus local.odysseus.apfel local.odysseus.chroma; do
    launchctl bootout "$DOMAIN/$a" 2>/dev/null || true
done
pkill -f 'uvicorn app:app' 2>/dev/null && echo "▶ stopped a running Odysseus server" || true
pkill -f 'bin/chroma run' 2>/dev/null && echo "▶ stopped a running ChromaDB" || true
pkill -f 'apfel --serve' 2>/dev/null && echo "▶ stopped a running Apfel server" || true
sleep 2
for p in "$PORT" "$CHROMA_PORT"; do
    if lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; then
        lsof -nP -iTCP:"$p" -sTCP:LISTEN
        fail "port $p is still in use by the process above - stop it and re-run"
    fi
done

# --- 2. Install and load ----------------------------------------------------
mkdir -p "$LA" "$REPO/logs"
for a in $AGENTS; do
    cp "$DIR/$a.plist" "$LA/$a.plist"
    diff -q "$DIR/$a.plist" "$LA/$a.plist" >/dev/null || fail "copy of $a.plist does not match"
    launchctl bootstrap "$DOMAIN" "$LA/$a.plist" || fail "launchctl bootstrap $a failed"
    launchctl enable "$DOMAIN/$a" 2>/dev/null || true
    echo "✓ $a loaded"
done

# --- 3. Verify they actually serve ------------------------------------------
echo "▶ Waiting for ChromaDB on :$CHROMA_PORT…"
ok=0
for _ in $(seq 1 30); do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "http://127.0.0.1:$CHROMA_PORT/api/v2/heartbeat" || true)"
    [ "$code" = "200" ] && { ok=1; break; }
    sleep 1
done
[ "$ok" = 1 ] && echo "✓ ChromaDB is up" || echo "⚠ ChromaDB not answering yet - see $REPO/logs/chroma-service.log"

echo "▶ Waiting for Odysseus on $URL (first start can take a minute)…"
for _ in $(seq 1 120); do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "$URL/" || true)"
    case "$code" in
    2??|3??)
        PID="$(launchctl list | awk '$3=="local.odysseus" {print $1}')"
        echo "✓ Odysseus is up at $URL (launchd PID: ${PID:-unknown})"
        echo
        echo "  Status  : launchctl list | grep local.odysseus"
        echo "  Restart : launchctl kickstart -k $DOMAIN/local.odysseus"
        echo "  Logs    : $REPO/logs/app-service.log  (app log: $REPO/data/logs/app.log)"
        echo "  Remove  : bash $DIR/uninstall.sh"
        exit 0 ;;
    esac
    sleep 1
done

echo "✗ No answer from $URL after 2 minutes. Diagnose with:"
echo "    launchctl print $DOMAIN/local.odysseus | grep -E 'state|last exit'"
echo "    tail -40 $REPO/logs/app-service.log"
exit 1
