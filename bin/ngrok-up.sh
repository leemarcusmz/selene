#!/usr/bin/env bash
# =============================================================================
# bin/ngrok-up.sh  v1.0  (2026-09-23)
# Runs the ngrok tunnel in the foreground for selene-ngrok.service (Linux).
# The reserved domain is machine-local config, read from v3.0/.env.local as
# NGROK_DOMAIN=xxxx.ngrok-free.app - never committed. The authtoken lives in
# ~/.config/ngrok/ngrok.yml (ngrok config add-authtoken, hub item wa4).
#
# Not gated on LIVE here; the unit that calls this carries
# ConditionPathExists=LIVE, and the free plan allows one live agent per
# account, so this must only ever run on the machine that is LIVE.
# =============================================================================
set -u
export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCAL="$ROOT/selene-dreams-script-v3.0/.env.local"
DOMAIN="$(grep -E '^NGROK_DOMAIN=' "$LOCAL" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'"' ')"
if [ -z "$DOMAIN" ]; then
  echo "$(date '+%F %T') ngrok-up: NGROK_DOMAIN missing from $LOCAL" >&2
  exit 1
fi
exec ngrok http --url="$DOMAIN" 5001 --log=stdout --log-format=logfmt
