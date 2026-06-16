#!/usr/bin/env bash
#
# Scheduled refresh runner. Triggered by launchd every 6 hours.
# Runs each pipeline stage separately and ALWAYS attempts the commit+push step
# at the end — partial data is better than no data. Each stage's exit code is
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
    echo "✗ $name: failed with exit code $rc — continuing"
  fi
}

# Each stage is its own ./tldr subcommand so a failure in one doesn't stop the next.
run_stage "ingest" ./tldr ingest
run_stage "dedup"  ./tldr dedup
run_stage "rank"   ./tldr rank
run_stage "blurbs" ./tldr blurbs all
run_stage "format" ./tldr format all
# Backtest cache: scrape TLDR's actual published issue for the target date
# (and the last few days) and store the comparison vs our predictions so the
# UI can render the recall dashboard without re-scraping at view time.
run_stage "backtest" ./tldr backtest_cache
# Learn from the backtest gap: update per-newsletter source-weight
# preferences so the next ranking run biases toward sources TLDR
# actually picks from.
run_stage "learn_weights" uv run python scripts/learn_source_weights.py

# Commit + push whatever data actually landed, even if some stages failed.
# That way the deployed Streamlit at least gets fresh raw/scored data even
# if blurbs crashed.
echo
echo "── COMMIT & PUSH ────────────────────────────"
git add data/scored data/blurbs data/issues 2>/dev/null || true
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
for stage in ingest dedup rank blurbs format backtest learn_weights; do
  printf "  %-8s %s\n" "$stage" "${STATUS[$stage]:-skipped}"
done
echo "▸ refresh complete: $(date)"
