#!/bin/bash
# =============================================================================
# install_reel_agent.command — install the trial-reel LaunchAgent
# VERSION 1.0 — 2026-09-09
#
# CHANGELOG
#   1.0  2026-09-09  First build.
#
# WHY A SCRIPT AND NOT A FILE DROPPED IN PLACE
#   ~/Library/LaunchAgents is outside every folder connected to Cowork, and
#   launchctl cannot be driven from there either. So this is delivered as a
#   script you double-click once.
#
# WHAT IT DOES
#   Installs com.selene.reel: every 15 minutes it POSTs /reel to the local
#   server, exactly like com.selene.publish does for the carousel lane. The
#   server decides whether anything is actually due; most pokes do nothing.
#
# TO UNINSTALL
#   launchctl bootout gui/$UID/com.selene.reel
#   rm ~/Library/LaunchAgents/com.selene.reel.plist
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.selene.reel.plist"
LABEL="com.selene.reel"

echo "Selene Dreams — trial reel agent installer v1.0"
echo

if [ ! -f "$HERE/.env" ]; then
  echo "ERROR: no .env found in $HERE"; exit 1
fi

SECRET="$(grep -E '^WEBHOOK_SECRET=' "$HERE/.env" | head -1 | cut -d= -f2- | tr -d '"'"'"' ')"
if [ -z "$SECRET" ]; then
  echo "ERROR: WEBHOOK_SECRET is not set in .env"; exit 1
fi

echo "Checking dependencies first..."
if ! /usr/bin/env python3 "$HERE/reel_runner.py" --doctor; then
  echo
  read -r -p "Dependencies are incomplete. Install the agent anyway? [y/N] " yn
  [[ "$yn" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }
fi

mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/curl</string>
    <string>-s</string>
    <string>-X</string><string>POST</string>
    <string>-H</string><string>Content-Type: application/json</string>
    <string>-d</string><string>{"secret":"${SECRET}"}</string>
    <string>http://127.0.0.1:5001/reel</string>
  </array>
  <key>StartInterval</key><integer>900</integer>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key>
  <string>${HOME}/Library/Logs/selene-reel.log</string>
  <key>StandardErrorPath</key>
  <string>${HOME}/Library/Logs/selene-reel.log</string>
</dict>
</plist>
PLISTEOF

chmod 600 "$PLIST"   # the plist carries the webhook secret

launchctl bootout "gui/$UID/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$PLIST"

echo
echo "Installed: $PLIST"
echo "Poking /reel every 15 minutes."
echo "Log: ~/Library/Logs/selene-reel.log"
echo
echo "REMINDER: like every other lane, this only runs while \"Start Selene AI\""
echo "is running. Restart it now so the server picks up v3.6 and the /reel route."
echo
read -r -p "Press return to close."
