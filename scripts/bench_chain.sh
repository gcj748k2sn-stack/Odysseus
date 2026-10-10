#!/bin/bash
# Run probes and benchmark runs one after another, unattended, switching model servers in between.
#
#   cd /Users/cedrik/odysseus && caffeinate -i scripts/bench_chain.sh                 # bonsai (short)
#   cd /Users/cedrik/odysseus && caffeinate -i scripts/bench_chain.sh bonsai-long     # ~3.5–5 h
#   cd /Users/cedrik/odysseus && caffeinate -i scripts/bench_chain.sh bonsai qwen     # phases in order
#   (--with-qwen = "bonsai qwen", kept for the first version's command)
#
# Needs Odysseus running. Asks for the Odysseus password once (or uses ODYSSEUS_PASSWORD).
# Each step logs to data/logs/chain-<start>/NN-<name>.log; a failed step is recorded and the
# chain goes on. Only one model server is up at a time (both together do not fit in 16 GB).
# Edit the step lists in bonsai_phase / qwen_phase below to change what runs.
# bash 3.2 compatible (macOS /bin/bash).

set -u
cd "$(dirname "$0")/.." || exit 1
REPO=$(pwd)
PY="$REPO/venv/bin/python"
STAMP=$(date +%Y%m%d-%H%M)
LOGDIR="$REPO/data/logs/chain-$STAMP"
mkdir -p "$LOGDIR"
SUMMARY="$LOGDIR/summary.txt"
PHASES="$*"
[ -z "$PHASES" ] && PHASES="bonsai"
[ "$PHASES" = "--with-qwen" ] && PHASES="bonsai qwen"
for p in $PHASES; do
  case "$p" in bonsai|bonsai-long|qwen) ;; *) echo "unknown phase: $p (bonsai, bonsai-long, qwen)"; exit 2;; esac
done

LMS=$(command -v lms || echo "$HOME/.lmstudio/bin/lms")
BONSAI_START="$HOME/BonsaiDemo/start_bonsai2.sh"
BONSAI_URL="http://127.0.0.1:8090"
LMSTUDIO_URL="http://127.0.0.1:1234"
QWEN_MODEL="qwen/qwen3.5-9b"

if [ -z "${ODYSSEUS_PASSWORD:-}" ]; then
  read -r -s -p "Odysseus password: " ODYSSEUS_PASSWORD; echo
fi
export ODYSSEUS_PASSWORD

n=0
note() { echo "$(date +%H:%M:%S) $*" | tee -a "$SUMMARY"; }

step() {                      # step NAME COMMAND...
  n=$((n + 1))
  local name="$1"; shift
  local log; log=$(printf "%s/%02d-%s.log" "$LOGDIR" "$n" "$name")
  note "▶ $name"
  local t0=$SECONDS
  "$@" > "$log" 2>&1
  local rc=$?
  local mins=$(( (SECONDS - t0) / 60 ))
  if [ $rc -eq 0 ]; then note "  ✓ $name (${mins} min)"; else note "  ✗ $name failed (exit $rc, ${mins} min) — see $log"; fi
  tail -3 "$log" | sed 's/^/    /' >> "$SUMMARY"
}

wait_for() {                  # wait_for URL SECONDS
  local url="$1" limit="$2" waited=0
  until curl -sf "$url/v1/models" > /dev/null 2>&1; do
    sleep 5; waited=$((waited + 5))
    [ $waited -ge "$limit" ] && return 1
  done
}

stop_lmstudio() { "$LMS" unload --all > /dev/null 2>&1; "$LMS" server stop > /dev/null 2>&1; sleep 3; }
stop_bonsai()   { pkill -f -- "--alias bonsai2-27b" > /dev/null 2>&1; sleep 5; }   # the server, not a probe

start_bonsai() {
  stop_lmstudio
  mkdir -p "$HOME/BonsaiDemo/logs"
  nohup "$BONSAI_START" > "$HOME/BonsaiDemo/logs/bonsai-$STAMP-chain.log" 2>&1 &
  wait_for "$BONSAI_URL" 300
}

start_qwen() {
  stop_bonsai
  "$LMS" server start > /dev/null 2>&1
  "$LMS" unload --all > /dev/null 2>&1
  "$LMS" load "$QWEN_MODEL" > /dev/null 2>&1
  wait_for "$LMSTUDIO_URL" 300
}

bench() { python3 scripts/bench_agent.py cleanup > /dev/null 2>&1; python3 scripts/bench_agent.py run "$@" --yes; }

bonsai_phase() {
  note "── Bonsai phase"
  if ! start_bonsai; then note "  ✗ Bonsai server did not come up in 5 min — phase skipped"; return; fi
  note "  Bonsai up"
  step bonsai-probe-nothink  "$PY" scripts/probe_direct_reply.py --url "$BONSAI_URL" --model bonsai2-27b \
       --variants odysseus --questions explain,price_now,calc --reps 2 --no-think
  step bonsai-probe-think    "$PY" scripts/probe_direct_reply.py --url "$BONSAI_URL" --model bonsai2-27b \
       --variants odysseus --questions explain,price_now,calc --reps 2
  step bonsai-knowledge-quick bench --target bonsai2 --suite knowledge --quick --runs 2
  stop_bonsai
  note "  Bonsai stopped"
}

bonsai_long_phase() {
  # Everything run on Qwen so far, on Bonsai: thinking-off probe, full knowledge, full agent
  # suite, research suite, then the prompt-variant probe (item 77) last, as it is the longest.
  note "── Bonsai long phase"
  if ! start_bonsai; then note "  ✗ Bonsai server did not come up in 5 min — phase skipped"; return; fi
  note "  Bonsai up"
  step bonsai-probe-nothink   "$PY" scripts/probe_direct_reply.py --url "$BONSAI_URL" --model bonsai2-27b \
       --variants odysseus --questions explain,price_now,obscure,calc --reps 2 --no-think
  step bonsai-knowledge-full  bench --target bonsai2 --suite knowledge --runs 2
  step bonsai-agent-full      bench --target bonsai2 --runs 2
  step bonsai-research        bench --target bonsai2 --suite research --runs 2
  step bonsai-probe-prompts   "$PY" scripts/probe_direct_reply.py --url "$BONSAI_URL" --model bonsai2-27b \
       --variants odysseus,og_refined,proposal_a,a_refined --questions explain,price_now,obscure,calc --reps 2
  stop_bonsai
  note "  Bonsai stopped"
}

qwen_phase() {
  note "── Qwen phase"
  if ! start_qwen; then note "  ✗ LM Studio / Qwen did not come up in 5 min — phase skipped"; return; fi
  note "  Qwen up"
  step qwen-knowledge-full   bench --target qwen35 --suite knowledge --runs 2
  step qwen-research         bench --target qwen35 --suite research --runs 2
}

note "chain started: $PHASES (logs: $LOGDIR)"
for p in $PHASES; do
  case "$p" in
    bonsai) bonsai_phase ;;
    bonsai-long) bonsai_long_phase ;;
    qwen) qwen_phase ;;
  esac
done
note "chain finished"
echo; cat "$SUMMARY"
