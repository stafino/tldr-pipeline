#!/usr/bin/env bash
#
# Scheduled refresh runner. Triggered by launchd every 6 hours.
# Runs the full pipeline (ingest → dedup → rank → blurbs → format) then
# commits + pushes the rendered issues so a deployed Streamlit can pick
# them up.
#
# Logs to data/logs/cron-YYYYMMDD-HHMM.log and rotates older logs.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# launchd runs with a minimal environment. Restore the basics so brew/uv/claude resolve.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin:$PATH"
export HOME="${HOME:-/Users/stovifo}"

# Load .env so LLM_BACKEND and any model overrides apply.
if [[ -f ".env" ]]; then
  set -a; source .env; set +a
fi

# Logging
mkdir -p data/logs
LOG="data/logs/cron-$(date +%Y%m%d-%H%M).log"
exec >>"$LOG" 2>&1

echo "═══════════════════════════════════════════════════════════════"
echo "▸ refresh start: $(date -u +%Y-%m-%dT%H:%M:%SZ) (local: $(date))"
echo "  REPO_ROOT=$REPO_ROOT"
echo "  LLM_BACKEND=${LLM_BACKEND:-api}"
echo "  PATH=$PATH"
echo "═══════════════════════════════════════════════════════════════"

# Run the pipeline.
./tldr refresh

# Optionally push results. Only if there's actually something to commit.
if git diff --quiet --exit-code -- data/blurbs data/scored data/issues 2>/dev/null; then
  echo "▸ no data changes; skipping commit"
else
  echo "▸ committing fresh issues to git"
  git add data/blurbs data/scored data/issues 2>/dev/null || true
  if [[ -n "$(git diff --cached --name-only)" ]]; then
    git -c user.email="${GIT_AUTHOR_EMAIL:-oliverstaf1@gmail.com}" \
        -c user.name="${GIT_AUTHOR_NAME:-stafino}" \
        commit -m "cron: refresh $(date -u +%Y-%m-%dT%H:%M:%SZ)" || true
    git push || echo "✗ push failed (will retry next run)"
  fi
fi

# Rotate logs: keep last 30 runs
ls -1t data/logs/cron-*.log 2>/dev/null | tail -n +31 | xargs -r rm -f

echo "▸ refresh complete: $(date)"
