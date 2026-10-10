#!/bin/bash
# Foreground entry point for the launchd agents in this folder.
#
#   run.sh app      Odysseus (uvicorn)         agent local.odysseus
#   run.sh chroma   ChromaDB on 127.0.0.1      agent local.odysseus.chroma
#   run.sh apfel    Apfel on :11435            agent local.odysseus.apfel
#
# Every mode ends in `exec`, so launchd is the direct parent of the server it
# supervises (a script that backgrounds the server and exits would be restarted
# forever). Settings come from .env exactly as in start-macos.sh.
# Runs under macOS /bin/bash 3.2: no bash-4 features.
set -u
MODE="${1:-}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR" || exit 1
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONUNBUFFERED=1

# launchd never rotates logs, so the script owns its log: keep one previous
# file, rotated at each (re)start once it passes 10 MB.
mkdir -p "$REPO_DIR/logs"
LOG="$REPO_DIR/logs/${MODE:-unknown}-service.log"
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG" | tr -d ' ')" -gt 10485760 ]; then
    mv -f "$LOG" "$LOG.1"
fi
exec >>"$LOG" 2>&1
echo "[$(date '+%F %T')] run.sh $MODE starting (pid $$)"

# .env loader, same rules as start-macos.sh: a variable already in the
# environment wins over .env.
if [ -f .env ]; then
    while IFS='=' read -r key value; do
        [[ "$key" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${key// }" ]] && continue
        value="${value%%#*}"
        value="${value#"${value%%[![:space:]]*}"}"
        value="${value%"${value##*[![:space:]]}"}"
        [ -n "$key" ] && [ -z "${!key+x}" ] && export "$key=$value"
    done < .env
fi

VENV_PY="$REPO_DIR/venv/bin/python3"
CHROMA_PORT="${CHROMADB_PORT:-8100}"

case "$MODE" in
app)
    PORT="${ODYSSEUS_PORT:-${APP_PORT:-7860}}"
    HOST="${ODYSSEUS_HOST:-${APP_BIND:-127.0.0.1}}"
    export APP_PORT="$PORT"   # the app builds its own URLs from APP_PORT

    # requirements.txt changed since the last install (e.g. after a merge):
    # install now. Same hash file as start-macos.sh, so the two stay in step.
    REQ_HASH="$(md5 -q requirements.txt 2>/dev/null)"
    if [ -n "$REQ_HASH" ] && [ "$REQ_HASH" != "$(cat venv/.requirements_hash 2>/dev/null)" ]; then
        echo "requirements.txt changed - installing"
        "$VENV_PY" -m pip install -r requirements.txt && echo "$REQ_HASH" > venv/.requirements_hash
    fi
    # ddgs (DuckDuckGo fallback) is not in requirements.txt; start-macos.sh
    # re-ensures it on every launch, so do the same.
    "$VENV_PY" -c 'import ddgs' >/dev/null 2>&1 || "$VENV_PY" -m pip install --quiet ddgs || true

    # At login both agents start together; give ChromaDB up to 30 s to listen
    # so the tool index is not built degraded.
    case "${CHROMADB_HOST:-localhost}" in
    localhost|127.0.0.1)
        for _ in $(seq 1 30); do
            (exec 3<>"/dev/tcp/127.0.0.1/$CHROMA_PORT") 2>/dev/null && break
            sleep 1
        done ;;
    esac

    echo "uvicorn on $HOST:$PORT"
    exec "$VENV_PY" -m uvicorn app:app --host "$HOST" --port "$PORT"
    ;;
chroma)
    case "${CHROMADB_HOST:-localhost}" in
    localhost|127.0.0.1) BIND="127.0.0.1" ;;
    0.0.0.0)             BIND="0.0.0.0" ;;
    *) echo "CHROMADB_HOST=${CHROMADB_HOST} is remote - nothing to run here"; sleep 3600; exit 0 ;;
    esac
    # Run the console script through the venv interpreter rather than its
    # shebang, so a rebuilt venv can't leave a stale interpreter path behind.
    exec "$VENV_PY" "$REPO_DIR/venv/bin/chroma" run --host "$BIND" --port "$CHROMA_PORT" --path "$REPO_DIR/data/chroma"
    ;;
apfel)
    APFEL_BIN="$(command -v apfel)" || { echo "apfel not installed"; sleep 3600; exit 1; }
    exec "$APFEL_BIN" --serve --port 11435
    ;;
*)
    echo "usage: run.sh app|chroma|apfel"; exit 2 ;;
esac
