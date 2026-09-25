#!/usr/bin/env bash
# =============================================================================
# bin/poke.sh  v1.2  (2026-09-25)
# v1.2: heartbeat. After each poke, ping healthchecks.io by slug
#       (https://hc-ping.com/$HC_PING_KEY/selene-<lane>): success when curl
#       exits 0 AND the server answered 2xx, /fail otherwise. HC_PING_KEY is
#       read from the same .env as WEBHOOK_SECRET; if it is missing the poke
#       still runs and a one-line note goes to stderr (no ping = the check
#       goes "down" on its own, which is the alert you want). The droplet is
#       never in the alert path: healthchecks -> Meta Graph API -> WhatsApp.
#       NOTE: /publish answers 200 "sweep started in background" — a green
#       ping means the scheduler + server are alive, not that the sweep
#       finished. Lane-level failures still show in selene-server.log.
# v1.1: bash shebang so the same file runs under launchd (Mac) and systemd
#       (droplet). ~/.local/bin on PATH. Logic unchanged.
# v1.0: (2026-09-21) one script behind all four poke agents.
# Reads WEBHOOK_SECRET from the v3.0 .env at run time, so no scheduler file
# ever carries a secret.
#
# LIVE GATE: does nothing until a file named LIVE exists at the repo root.
# That file is created by hand at cutover and is gitignored, so a fresh clone
# on any machine is inert until someone decides otherwise. This is the guard
# against two machines publishing at once.
#
# Usage: poke.sh publish | reel | research | edu
# =============================================================================
set -u
export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV="$ROOT/selene-dreams-script-v3.0/.env"
LANE="${1:?usage: poke.sh publish|reel|research|edu}"

[ -f "$ROOT/LIVE" ] || exit 0

envval(){ grep -E "^$1=" "$ENV" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'"' '; }
SECRET="$(envval WEBHOOK_SECRET)"
if [ -z "$SECRET" ]; then
  echo "$(date '+%F %T') $LANE: WEBHOOK_SECRET missing from $ENV" >&2
  exit 1
fi
PING_KEY="$(envval HC_PING_KEY)"

case "$LANE" in
  publish)  URL="http://127.0.0.1:5001/publish"  ;;
  reel)     URL="http://127.0.0.1:5001/reel"     ;;
  research) URL="http://127.0.0.1:5001/research" ;;
  edu)      URL="http://127.0.0.1:5002/tick"     ;;
  *) echo "poke.sh: unknown lane '$LANE'" >&2; exit 2 ;;
esac

# -m 840: always finish inside the 900s interval so pokes never overlap.
CODE="$(/usr/bin/curl -s -m 840 -o /dev/stdout -w '\n%{http_code}' -X POST \
  -H 'Content-Type: application/json' \
  -d "{\"secret\":\"$SECRET\"}" "$URL")"
RC=$?
HTTP="${CODE##*$'\n'}"
BODY="${CODE%$'\n'*}"
printf '%s\n' "$BODY"

if [ -z "$PING_KEY" ]; then
  echo "$(date '+%F %T') $LANE: HC_PING_KEY missing from $ENV — no heartbeat ping" >&2
  exit $RC
fi
if [ "$RC" -eq 0 ] && [ "${HTTP:0:1}" = "2" ]; then
  /usr/bin/curl -fsS -m 10 --retry 3 -o /dev/null "https://hc-ping.com/$PING_KEY/selene-$LANE" \
    || echo "$(date '+%F %T') $LANE: hc ping failed" >&2
else
  /usr/bin/curl -fsS -m 10 --retry 3 -o /dev/null --data-raw "curl=$RC http=$HTTP ${BODY:0:300}" \
    "https://hc-ping.com/$PING_KEY/selene-$LANE/fail" || true
fi
exit $RC
