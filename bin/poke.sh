#!/bin/zsh
# =============================================================================
# bin/poke.sh  v1.0  (2026-09-21)
# One script behind all four poke agents. Reads WEBHOOK_SECRET from the v3.0
# .env at run time, so no plist ever carries a secret again (p2e).
#
# LIVE GATE: does nothing until a file named LIVE exists at the repo root.
# That file is created by hand at cutover (Phase 7) and is gitignored, so a
# fresh clone on any machine is inert until someone decides otherwise. This is
# the guard against two machines publishing at once.
#
# Usage: poke.sh publish | reel | research | edu
# =============================================================================
set -u
export PATH="/usr/local/bin:$PATH"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV="$ROOT/selene-dreams-script-v3.0/.env"
LANE="${1:?usage: poke.sh publish|reel|research|edu}"

[ -f "$ROOT/LIVE" ] || exit 0

SECRET="$(grep -E '^WEBHOOK_SECRET=' "$ENV" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'"' ')"
if [ -z "$SECRET" ]; then
  echo "$(date '+%F %T') $LANE: WEBHOOK_SECRET missing from $ENV" >&2
  exit 1
fi

case "$LANE" in
  publish)  URL="http://127.0.0.1:5001/publish"  ;;
  reel)     URL="http://127.0.0.1:5001/reel"     ;;
  research) URL="http://127.0.0.1:5001/research" ;;
  edu)      URL="http://127.0.0.1:5002/tick"     ;;
  *) echo "poke.sh: unknown lane '$LANE'" >&2; exit 2 ;;
esac

# -m 840: always finish inside the 900s StartInterval so pokes never overlap.
exec /usr/bin/curl -s -m 840 -X POST \
  -H 'Content-Type: application/json' \
  -d "{\"secret\":\"$SECRET\"}" "$URL"
