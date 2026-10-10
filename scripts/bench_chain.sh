#!/bin/bash
# Run probes and benchmark runs one after another, unattended, switching model servers in between.
#
#   cd /Users/cedrik/odysseus && caffeinate -i scripts/bench_chain.sh                 # bonsai (short)
#   cd /Users/cedrik/odysseus && caffeinate -i scripts/bench_chain.sh bonsai-long     # ~3.5–5 h
#   cd /Users/cedrik/odysseus && caffeinate -i scripts/bench_chain.sh bonsai qwen     # phases in order
#   cd /Users/cedrik/odysseus && caffeinate -i scripts/bench_chain.sh qwen-full bonsai-check   # ~4–5 h
#   cd /Users/cedrik/odysseus && caffeinate -i scripts/bench_chain.sh full          # qwen-full bonsai-full, ~6–8 h
#   BENCH_POWER=1 ...bench_chain.sh full      also records power in watts (asks for the Mac password once)
#
# While it runs, scripts/bench_sysmon.py samples CPU, GPU, memory, swap, thermal state and the
# servers' memory every 10 s into the log folder (sysmon.jsonl, env.json); summary.txt ends with
# a per-step table, and app.log plus the Bonsai log are copied there after each phase.
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
[ "$PHASES" = "full" ] && PHASES="qwen-full bonsai-full"
for p in $PHASES; do
  case "$p" in bonsai|bonsai-long|bonsai-check|bonsai-full|qwen|qwen-full) ;;
    *) echo "unknown phase: $p (full, bonsai, bonsai-long, bonsai-check, bonsai-full, qwen, qwen-full)"; exit 2;; esac
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
  echo "$name" > "$LOGDIR/current_step"
  local t0=$SECONDS
  "$@" > "$log" 2>&1
  local rc=$?
  echo "-" > "$LOGDIR/current_step"
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
  return 0                    # an until loop returns its body's last status, i.e. the failed test above
}

stop_lmstudio() { "$LMS" unload --all > /dev/null 2>&1; "$LMS" server stop > /dev/null 2>&1; sleep 3; }
stop_bonsai() {                # the server, not a probe; wait until the port is free
  pkill -f -- "--alias bonsai2-27b" > /dev/null 2>&1; sleep 5
  local i=0
  while curl -sf "$BONSAI_URL/v1/models" > /dev/null 2>&1 && [ $i -lt 10 ]; do sleep 3; i=$((i + 1)); done
}

start_bonsai() {               # start_bonsai [extra llama-server flags, appended last so they win]
  stop_bonsai                 # a Bonsai left running would mean two 27B models in 16 GB
  stop_lmstudio
  mkdir -p "$HOME/BonsaiDemo/logs"
  nohup "$BONSAI_START" "$@" >> "$HOME/BonsaiDemo/logs/bonsai-$STAMP-chain.log" 2>&1 &
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

# Code changed since Odysseus started would not be in the runs, and they would be
# labelled with the new HEAD anyway. Seconds since start, from ps's [[dd-]hh:]mm:ss.
odysseus_is_fresh() {
  local pid etime age newest
  pid=$(pgrep -f "uvicorn app:app" | head -1)
  [ -z "$pid" ] && { note "  ✗ Odysseus is not running (launchctl kickstart gui/\$(id -u)/local.odysseus)"; return 1; }
  etime=$(ps -o etime= -p "$pid" | tr -d ' ')
  age=$(echo "$etime" | awk -F'[-:]' '{ s=0; m=1; for (i=NF; i>0; i--) { s+=$i*m; m=(m==3600?86400:m*60) } print s }')
  newest=$(find src core routes services app.py -name '*.py' -print0 2>/dev/null | xargs -0 stat -f %m | sort -n | tail -1)
  if [ -n "$newest" ] && [ $(( $(date +%s) - age )) -lt "$newest" ]; then
    note "  ✗ Odysseus started before the latest code change — restart it first:"
    note "    launchctl kickstart -k gui/\$(id -u)/local.odysseus   (wait ~20 s, then start the chain again)"
    return 1
  fi
  return 0
}

bonsai_phase() {
  note "── Bonsai phase"
  if ! start_bonsai; then note "  ✗ Bonsai server did not come up in 5 min — phase skipped"; stop_bonsai; return; fi
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
  if ! start_bonsai; then note "  ✗ Bonsai server did not come up in 5 min — phase skipped"; stop_bonsai; return; fi
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

copy_logs() {                 # app.log rotates at 5 MB; keep this chain's evidence with it
  mkdir -p "$LOGDIR/logs"
  cp -p "$REPO"/data/logs/app.log* "$LOGDIR/logs/" 2>/dev/null
  cp -p "$HOME/BonsaiDemo/logs/bonsai-$STAMP-chain.log" "$LOGDIR/logs/" 2>/dev/null
  return 0
}

start_monitor() {
  python3 scripts/bench_sysmon.py env --out "$LOGDIR" > /dev/null 2>&1
  echo "-" > "$LOGDIR/current_step"
  nohup python3 scripts/bench_sysmon.py sample --out "$LOGDIR" --interval 10 --until-pid $$ \
    > "$LOGDIR/sysmon.err" 2>&1 &
  if [ "${BENCH_POWER:-0}" = "1" ]; then
    # powermetrics needs root. One password prompt now; a root watcher stops it when this shell exits.
    if sudo -v; then
      sudo -b sh -c "powermetrics -i 10000 --samplers cpu_power,gpu_power,thermal -o '$LOGDIR/powermetrics.txt' > /dev/null 2>&1 & pm=\$!; while kill -0 $$ 2>/dev/null; do sleep 15; done; kill \$pm"
      note "power: powermetrics every 10 s"
    else
      note "power: sudo refused — running without watts"
    fi
  fi
}

bonsai_full_phase() {
  # Everything at medium (agent, knowledge, research ×2), then knowledge ×2 with thinking off.
  note "── Bonsai full phase"
  if ! start_bonsai; then note "  ✗ Bonsai server did not come up in 5 min — phase skipped"; stop_bonsai; return; fi
  note "  Bonsai up (medium)"
  step bonsai-agent-full      bench --target bonsai2 --runs 2
  step bonsai-knowledge-full  bench --target bonsai2 --suite knowledge --runs 2
  step bonsai-research        bench --target bonsai2 --suite research --runs 2
  if ! start_bonsai --chat-template-kwargs '{"enable_thinking":false}'; then
    note "  ✗ Bonsai (thinking off) did not come up — rest of phase skipped"; stop_bonsai; copy_logs; return
  fi
  note "  Bonsai up (thinking off)"
  step bonsai-nothink-knowledge-full bench --target bonsai2 --suite knowledge --runs 2
  stop_bonsai
  note "  Bonsai stopped"
  copy_logs
}

bonsai_check_phase() {
  # After the 2026-10-10 fixes: research on medium (the run that broke at task 2),
  # then the knowledge suite with thinking switched off (the probe: 10x faster, calc right).
  note "── Bonsai check phase"
  if ! start_bonsai; then note "  ✗ Bonsai server did not come up in 5 min — phase skipped"; stop_bonsai; return; fi
  note "  Bonsai up (medium)"
  step bonsai-research        bench --target bonsai2 --suite research --runs 1
  if ! start_bonsai --chat-template-kwargs '{"enable_thinking":false}'; then
    note "  ✗ Bonsai (thinking off) did not come up — rest of phase skipped"; stop_bonsai; return
  fi
  note "  Bonsai up (thinking off)"
  step bonsai-nothink-knowledge-full bench --target bonsai2 --suite knowledge --runs 2
  stop_bonsai
  note "  Bonsai stopped"
}

qwen_full_phase() {
  note "── Qwen full phase"
  if ! start_qwen; then note "  ✗ LM Studio / Qwen did not come up in 5 min — phase skipped"; return; fi
  note "  Qwen up"
  step qwen-agent-full       bench --target qwen35 --runs 2
  step qwen-knowledge-full   bench --target qwen35 --suite knowledge --runs 2
  step qwen-research         bench --target qwen35 --suite research --runs 2
  stop_lmstudio
  note "  LM Studio stopped"
  copy_logs
}

qwen_phase() {
  note "── Qwen phase"
  if ! start_qwen; then note "  ✗ LM Studio / Qwen did not come up in 5 min — phase skipped"; return; fi
  note "  Qwen up"
  step qwen-knowledge-full   bench --target qwen35 --suite knowledge --runs 2
  step qwen-research         bench --target qwen35 --suite research --runs 2
}

note "chain started: $PHASES (logs: $LOGDIR)"
odysseus_is_fresh || exit 1
start_monitor
for p in $PHASES; do
  case "$p" in
    bonsai) bonsai_phase ;;
    bonsai-long) bonsai_long_phase ;;
    bonsai-check) bonsai_check_phase ;;
    bonsai-full) bonsai_full_phase ;;
    qwen) qwen_phase ;;
    qwen-full) qwen_full_phase ;;
  esac
done
note "chain finished"
copy_logs
{ echo; echo "System load per step (bench_sysmon.py; thermal 0 nominal … 3 critical; W only with BENCH_POWER=1):"
  python3 scripts/bench_sysmon.py summary "$LOGDIR"; } >> "$SUMMARY" 2>&1
echo; cat "$SUMMARY"
