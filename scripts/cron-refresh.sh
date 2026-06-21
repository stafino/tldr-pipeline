#!/usr/bin/env bash
#
# Scheduled refresh runner. Triggered by launchd every 6 hours.
# Runs each pipeline stage separately and ALWAYS attempts the commit+push step
# at the end - partial data is better than no data. Each stage's exit code is
# captured so a failure in one stage doesn't abort the rest.
#
# Logs to data/logs/cron-YYYYMMDD-HHMM.log; older logs are rotated.

set -o pipefail   # NB: no -e (continue past failures) and no -u (assoc-array
                  # indexing under set -u is brittle on some bash builds)

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# launchd runs with a minimal environment. Restore the basics.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin:$PATH"
export HOME="${HOME:-/Users/stovifo}"
# Unbuffered Python so tracebacks flush completely before the process exits
# (the overnight 03:46 crash had a truncated traceback because of buffering).
export PYTHONUNBUFFERED=1

# Load .env so LLM_BACKEND etc. apply.
if [[ -f ".env" ]]; then
  set -a; source .env; set +a
fi

mkdir -p data/logs
LOG="data/logs/cron-$(date +%Y%m%d-%H%M).log"
exec >>"$LOG" 2>&1

echo "═══════════════════════════════════════════════════════════════"
echo "▸ refresh start: $(date -u +%Y-%m-%dT%H:%M:%SZ) (local: $(date))"
echo "  REPO_ROOT=$REPO_ROOT"
echo "  LLM_BACKEND=${LLM_BACKEND:-api}"
echo "  PYTHONUNBUFFERED=$PYTHONUNBUFFERED"
echo "═══════════════════════════════════════════════════════════════"

# Track per-stage status so we can report at the end.
declare -A STATUS

run_stage() {
  local name="$1"; shift
  echo
  echo "── STAGE: $name ─────────────────────────────"
  if "$@"; then
    STATUS[$name]="ok"
    echo "▸ $name: ok"
  else
    local rc=$?
    STATUS[$name]="failed (rc=$rc)"
    echo "✗ $name: failed with exit code $rc - continuing"
  fi
}

# Background variant: spawn the command to its own log, return immediately.
# Pair with wait_stage <name> to block + replay the log + record exit code.
run_stage_bg() {
  local name="$1"; shift
  local logfile="/tmp/cron-stage-$name.log"
  echo "  → $name started in parallel"
  (
    echo "── STAGE: $name (parallel) ──────────────────"
    if "$@"; then
      echo "▸ $name: ok"
    else
      local rc=$?
      echo "✗ $name: failed with exit code $rc"
      exit $rc
    fi
  ) > "$logfile" 2>&1 &
  echo $! > "/tmp/cron-pid-$name"
}

wait_stage() {
  local name="$1"
  local pid
  pid=$(cat "/tmp/cron-pid-$name" 2>/dev/null) || return
  if wait "$pid"; then
    STATUS[$name]="ok"
  else
    STATUS[$name]="failed (rc=$?)"
  fi
  # Replay the stage's log inline so it appears in the main cron log
  cat "/tmp/cron-stage-$name.log" 2>/dev/null
  rm -f "/tmp/cron-stage-$name.log" "/tmp/cron-pid-$name"
}

# ─── Sequential prereqs ─────────────────────────────────────────────
# ingest → dedup → rank produces data/scored/<date>.jsonl which every
# downstream stage reads. Has to be serial.
run_stage "ingest" ./tldr ingest
run_stage "dedup"  ./tldr dedup
run_stage "rank"   ./tldr rank

# ─── Parallel fan-out ───────────────────────────────────────────────
# blurbs, funding, vc, backtest all read data/scored and write to
# disjoint paths. Fire them concurrently and wait for all to finish.
# The Claude Code CLI handles ~20 simultaneous calls fine, which is
# the worst-case sum of these stages' internal concurrency.
echo
echo "── PARALLEL FAN-OUT (blurbs + funding + vc + backtest) ──"
run_stage_bg "blurbs"   ./tldr blurbs all
run_stage_bg "funding"  ./tldr funding
run_stage_bg "vc"       ./tldr vc
run_stage_bg "backtest" ./tldr backtest_cache

wait_stage "blurbs"
wait_stage "funding"
wait_stage "vc"
wait_stage "backtest"

# ─── Sequential post-deps ───────────────────────────────────────────
# format needs blurbs done. learn_weights needs backtest done.
run_stage "format" ./tldr format all
run_stage "learn_weights" uv run python scripts/learn_source_weights.py

# Commit + push whatever data actually landed, even if some stages failed.
# That way the deployed Streamlit at least gets fresh raw/scored data even
# if blurbs crashed.
echo
echo "── COMMIT & PUSH ────────────────────────────"
git add data/scored data/blurbs data/issues data/funding data/vc data/backtest 2>/dev/null || true
if [[ -n "$(git diff --cached --name-only)" ]]; then
  git -c user.email="${GIT_AUTHOR_EMAIL:-oliverstaf1@gmail.com}" \
      -c user.name="${GIT_AUTHOR_NAME:-stafino}" \
      commit -m "cron: refresh $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      && git push \
      || echo "✗ commit/push failed (will retry next run)"
else
  echo "▸ no data changes; nothing to commit"
fi

# Rotate logs: keep the last 30 runs
ls -1t data/logs/cron-*.log 2>/dev/null | tail -n +31 | xargs -r rm -f

echo
echo "── SUMMARY ──────────────────────────────────"
for stage in ingest dedup rank blurbs funding vc backtest format learn_weights; do
  printf "  %-8s %s\n" "$stage" "${STATUS[$stage]:-skipped}"
done
echo "▸ refresh complete: $(date)"
