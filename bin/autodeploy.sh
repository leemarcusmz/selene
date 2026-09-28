#!/usr/bin/env bash
# =============================================================================
# bin/autodeploy.sh  v1.0  (2026-09-28)
# Pull production and deploy it, only when GitHub has something new.
# Run by selene-deploy.timer every 5 minutes (systemd user unit, Linux only).
#
# WHY: the 2026-09-28 pushes sat undeployed until Marcus ran deploy.sh by
# hand; ~/runner/bin/deploy-all.sh never fired on its own. A push to
# `production` now reaches the VPS within 5 minutes, and deploy.sh restarts
# the servers (only on the LIVE machine), so new code never sits dead.
#
# SAFETY: fast-forward only. A local edit that diverged from production makes
# the pull fail LOUDLY in the log instead of being overwritten or merged.
# Nothing here publishes anything; deploy.sh's LIVE gate is unchanged.
# =============================================================================
set -u
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BRANCH="production"
say(){ echo "$(date '+%F %T') autodeploy: $*"; }

cd "$ROOT" || { say "repo missing at $ROOT"; exit 1; }
git fetch -q origin "$BRANCH" 2>&1 || { say "fetch FAILED (network or auth)"; exit 1; }
LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse "origin/$BRANCH")"
[ "$LOCAL" = "$REMOTE" ] && exit 0          # quiet when nothing changed

say "new production ${LOCAL:0:7} -> ${REMOTE:0:7}"
if ! git merge -q --ff-only "origin/$BRANCH" 2>&1; then
  say "pull FAILED — local changes diverged from $BRANCH; fix by hand (git status)"
  exit 1
fi
if ./deploy.sh; then
  say "deployed ${REMOTE:0:7} OK"
else
  say "deploy.sh FAILED at ${REMOTE:0:7} — servers may be on old code; run ./deploy.sh by hand"
  exit 1
fi
