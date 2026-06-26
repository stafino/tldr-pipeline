#!/usr/bin/env bash
#
# install-launchd.sh — install the tldr-pipeline cron refresh as a launchd
# user agent on the current Mac.
#
# Generates a per-machine plist (paths/HOME substituted from the current
# environment) at ~/Library/LaunchAgents/com.tldr.pipeline.refresh.plist,
# unloads any previous version, and loads the new one. RunAtLoad=true, so
# the first refresh fires immediately after this script exits.
#
# To uninstall:
#   launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.tldr.pipeline.refresh.plist
#   rm ~/Library/LaunchAgents/com.tldr.pipeline.refresh.plist

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.tldr.pipeline.refresh"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
UID_NUM="$(id -u)"

mkdir -p "$HOME/Library/LaunchAgents" "$REPO_ROOT/data/logs"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>

    <key>ProgramArguments</key>
    <array>
        <string>$REPO_ROOT/scripts/cron-refresh.sh</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$REPO_ROOT</string>

    <key>StartInterval</key>
    <integer>21600</integer>

    <key>RunAtLoad</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$REPO_ROOT/data/logs/launchd.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$REPO_ROOT/data/logs/launchd.stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin</string>
        <key>HOME</key>
        <string>$HOME</string>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
    </dict>

    <key>AbandonProcessGroup</key>
    <false/>
</dict>
</plist>
EOF

# Replace any existing copy. bootout is a no-op if not loaded.
launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$UID_NUM" "$PLIST"

echo "▸ installed and loaded: $PLIST"
launchctl print "gui/$UID_NUM/$LABEL" | grep -E "state|last exit|next firing|path" | head -10
