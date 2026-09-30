#!/usr/bin/env bash
# =============================================================================
# bin/research-watchdog.sh  v1.0  (2026-09-30)
# Did this week's research land? Answers from the droplet itself, with the
# droplet's own GitHub token — no cloud task, no Mac, no credential anywhere
# but github_token.txt (Runner Hub p8e, "runner-injected token").
#
# Checks the memory repo for the week's three artefacts:
#   candidates/candidates-WEEK.json   research finished
#   shortlists/shortlist-WEEK.json    visual screening finished
#   reports/research-report-WEEK.md   report published
# and pings healthchecks.io: success when all three exist, /fail otherwise,
# with a one-line diagnosis as the ping body (healthchecks shows it in the
# alert). The alert path is the existing one — healthchecks -> Meta Graph API
# -> WhatsApp — so the droplet is still not in the alert path. Slug: the
# existing weekly `selene-research` check (created by nora bin/hc_setup.py).
#
# Fires Mon 18:00 HKT from selene-watchdog.timer. LIVE-gated like poke.sh.
# Usage: research-watchdog.sh [WEEK]     (WEEK = Monday, YYYY-MM-DD; default
#                                         the most recent Monday)
# =============================================================================
set -u
export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
V3="$ROOT/selene-dreams-script-v3.0"
ENV="$V3/.env"
SLUG="selene-research"
REPO="leemarcusmz/selene-ig-memory"

[ -f "$ROOT/LIVE" ] || exit 0

stamp(){ date '+%F %T'; }
envval(){ grep -E "^$1=" "$ENV" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'"' '; }

WEEK="${1:-$(date -d "last monday" +%F 2>/dev/null)}"
# `date -d "last monday"` on a Monday gives LAST week; correct it.
[ "$(date +%u)" = 1 ] && [ -z "${1:-}" ] && WEEK="$(date +%F)"

TOKEN="$(cat "$V3/github_token.txt" 2>/dev/null)"
PING_KEY="$(envval HC_PING_KEY)"

ping_hc(){ # $1 = "" or "/fail", $2 = body
  [ -z "$PING_KEY" ] && { echo "$(stamp) watchdog: HC_PING_KEY missing — no ping sent" >&2; return; }
  curl -fsS -m 10 --retry 3 -X POST --data-raw "$2" \
    "https://hc-ping.com/$PING_KEY/$SLUG$1" >/dev/null 2>&1 \
    || echo "$(stamp) watchdog: healthchecks ping$1 failed" >&2
}

if [ -z "$TOKEN" ]; then
  MSG="research watchdog $WEEK: github_token.txt missing on the runner"
  echo "$(stamp) $MSG"; ping_hc /fail "$MSG"; exit 1
fi

missing=(); codes=()
for f in "candidates/candidates-$WEEK.json" "shortlists/shortlist-$WEEK.json" \
         "reports/research-report-$WEEK.md"; do
  code="$(curl -s -m 20 -o /dev/null -w '%{http_code}' \
          -H "Authorization: token $TOKEN" -H 'Accept: application/vnd.github+json' \
          "https://api.github.com/repos/$REPO/contents/$f")"
  codes+=("$f=$code")
  [ "$code" = 200 ] || missing+=("$f ($code)")
done

if [ ${#missing[@]} -eq 0 ]; then
  MSG="research watchdog $WEEK: candidates, shortlist and report all present"
  echo "$(stamp) $MSG"; ping_hc "" "$MSG"; exit 0
fi

# A non-404 on every file means GitHub or the token, not the pipeline.
if ! printf '%s\n' "${codes[@]}" | grep -q '=404$' && \
   ! printf '%s\n' "${codes[@]}" | grep -q '=200$'; then
  MSG="research watchdog $WEEK: GitHub API answered ${codes[*]} — token or GitHub problem, not the pipeline"
else
  MSG="research watchdog $WEEK: MISSING ${missing[*]}. Recover: ssh vps 'systemctl --user start selene-research.service'; watch ~/runner/logs/selene-research.log. Shortlist missing alone = screener (/screen poke) — see selene-server.log."
fi
echo "$(stamp) $MSG"
ping_hc /fail "$MSG"
exit 2
