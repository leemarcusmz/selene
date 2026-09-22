#!/bin/zsh
# =============================================================================
# deploy.sh  v1.2  (2026-09-22)
# v1.2: decrypt selene-dreams-script-v3.0/.env.age beside itself. The shared
#       runner only decrypts a root-level .env.age; Selene's .env lives one
#       level down where config.py and config_edu.py read it.
# v1.1: explicit /usr/local/bin/python3 (a bare ssh shell finds Apple CLT python
#       first) and --only-binary=:all: - an unattended runner never compiles.
#       Found when cryptography tried to build from source on Intel + 3.13.
# Called by ~/runner/bin/deploy-all.sh on the runner after every change to the
# production branch. Must be idempotent: running it twice changes nothing.
#
#   1. install/refresh Python deps from v3.0's requirements.txt (covers both
#      lanes - educational imports v3.0's modules and shares its .env)
#   2. render every agents/*.plist (__HOME__ -> real home), install only the
#      ones that changed, (re)load them
#   3. if LIVE exists, require the 5001 server to answer /health
#
# NOT here yet: com.selene.server and com.selene.ngrok (Phase 6). Adding an
# ngrok agent before cutover would steal the reserved domain from the MacBook.
# =============================================================================
set -eu
export PATH="/usr/local/bin:$PATH"
ROOT="$(cd "$(dirname "$0")" && pwd)"
say(){ echo "$(date '+%F %T') selene: $*"; }

say "deps"
/usr/local/bin/python3 -m pip install -q --user --only-binary=:all: -r "$ROOT/selene-dreams-script-v3.0/requirements.txt" \
  || { say "pip install FAILED"; exit 1; }

say "secrets"
V3="$ROOT/selene-dreams-script-v3.0"
if [ -f "$V3/.env.age" ]; then
  age -d -i "$HOME/runner/keys/runner.age" -o "$V3/.env" "$V3/.env.age" && chmod 600 "$V3/.env" \
    || { say "age decrypt FAILED"; exit 1; }
else
  say "no .env.age yet - skipping"
fi

say "agents"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
chmod +x "$ROOT"/bin/*.sh
for tpl in "$ROOT"/agents/*.plist; do
  name="$(basename "$tpl")"; label="${name%.plist}"
  dst="$HOME/Library/LaunchAgents/$name"
  sed "s|__HOME__|$HOME|g" "$tpl" > "$dst.new"
  plutil -lint -s "$dst.new" || { say "$label: plist invalid"; rm -f "$dst.new"; exit 1; }
  if [ -f "$dst" ] && cmp -s "$dst" "$dst.new"; then rm -f "$dst.new"; continue; fi
  mv "$dst.new" "$dst"; chmod 600 "$dst"
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$dst"
  say "$label (re)loaded"
done

if [ -f "$ROOT/LIVE" ]; then
  curl -sf -m 5 http://127.0.0.1:5001/health >/dev/null \
    && say "5001 healthy" || { say "5001 NOT answering /health"; exit 1; }
else
  say "not LIVE - agents installed but poke.sh is inert"
fi
say "ok"
