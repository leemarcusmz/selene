#!/usr/bin/env bash
# =============================================================================
# deploy.sh  v2.0.1  (2026-09-23)
# v2.0.1: the educational SERVER unit is selene-edu-server.service. v2.0 named
#         it selene-edu.service, which collided with the edu *poke* unit of the
#         same name - the poke won and the 5002 server was never installed.
# v2.0: one script, two operating systems. `uname -s` picks the branch.
#         Linux  (the DigitalOcean droplet, Ubuntu 24.04): deps go into a venv
#                at $ROOT/.venv (PEP 668 forbids pip --user on Ubuntu); units
#                from agents/systemd/ are installed as systemd *user* units;
#                servers are restarted only when LIVE exists.
#         Darwin (the Intel Mac, the warm spare): the v1.2 path, unchanged -
#                pip --user with /usr/local/bin/python3, launchd plists from
#                agents/*.plist. The Mac never sees agents/systemd/.
#       Shebang is bash, not zsh: macOS ships bash 3.2, so nothing below uses
#       bash-4 features. Never name a variable `status`.
# v1.2: decrypt selene-dreams-script-v3.0/.env.age beside itself.
# v1.1: explicit /usr/local/bin/python3 and --only-binary=:all:.
#
# Called by ~/runner/bin/deploy-all.sh after every change to the production
# branch. Must be idempotent: running it twice changes nothing.
#
#   1. deps      install/refresh Python deps from v3.0's requirements.txt
#   2. secrets   decrypt v3.0/.env.age -> v3.0/.env (600)
#   3. agents    install the scheduler units for this OS, only what changed
#   4. LIVE      if LIVE exists: (Linux) restart the servers, then require
#                5001 to answer /health. Otherwise say so and exit 0.
#
# The LIVE gate: bin/poke.sh is inert and the Linux server/ngrok units carry
# ConditionPathExists=LIVE, so a machine without that file installs everything
# and runs nothing that publishes. LIVE exists on exactly one machine.
# =============================================================================
set -eu
OS="$(uname -s)"
ROOT="$(cd "$(dirname "$0")" && pwd)"
V3="$ROOT/selene-dreams-script-v3.0"
say(){ echo "$(date '+%F %T') selene: $*"; }

# ---------------------------------------------------------------- 1. deps ---
say "deps ($OS)"
if [ "$OS" = "Linux" ]; then
  export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"
  if [ ! -x "$ROOT/.venv/bin/python" ]; then
    say "creating venv at .venv"
    python3 -m venv "$ROOT/.venv" || { say "venv creation FAILED (sudo apt-get install python3-venv)"; exit 1; }
  fi
  PY="$ROOT/.venv/bin/python"
  "$PY" -m pip install -q --only-binary=:all: -r "$V3/requirements.txt" \
    || { say "pip install FAILED"; exit 1; }
else
  export PATH="/usr/local/bin:$PATH"
  /usr/local/bin/python3 -m pip install -q --user --only-binary=:all: -r "$V3/requirements.txt" \
    || { say "pip install FAILED"; exit 1; }
fi

# ------------------------------------------------------------- 2. secrets ---
say "secrets"
if [ -f "$V3/.env.age" ]; then
  age -d -i "$HOME/runner/keys/runner.age" -o "$V3/.env" "$V3/.env.age" && chmod 600 "$V3/.env" \
    || { say "age decrypt FAILED"; exit 1; }
else
  say "no .env.age yet - skipping"
fi
chmod +x "$ROOT"/bin/*.sh

# -------------------------------------------------------------- 3. agents ---
if [ "$OS" = "Linux" ]; then
  say "agents (systemd user units)"
  UNITS="$HOME/.config/systemd/user"
  mkdir -p "$UNITS" "$HOME/runner/logs"
  changed=0
  for src in "$ROOT"/agents/systemd/*.service "$ROOT"/agents/systemd/*.timer; do
    [ -f "$src" ] || continue
    name="$(basename "$src")"; dst="$UNITS/$name"
    if [ -f "$dst" ] && cmp -s "$src" "$dst"; then continue; fi
    cp "$src" "$dst"; chmod 644 "$dst"; changed=1
    say "$name installed"
  done
  [ "$changed" = 1 ] && systemctl --user daemon-reload
  # Timers run always (poke.sh is inert without LIVE). Services are enabled so
  # they come back after a reboot, but their ConditionPathExists=LIVE keeps
  # them stopped on a machine that is not LIVE.
  for t in "$ROOT"/agents/systemd/*.timer; do
    systemctl --user enable -q --now "$(basename "$t")"
  done
  for s in selene-server.service selene-edu-server.service selene-ngrok.service; do
    [ -f "$UNITS/$s" ] && systemctl --user enable -q "$s"
  done
else
  say "agents (launchd)"
  mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
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
fi

# ---------------------------------------------------------------- 4. LIVE ---
if [ -f "$ROOT/LIVE" ]; then
  if [ "$OS" = "Linux" ]; then
    say "LIVE - restarting servers"
    systemctl --user restart selene-server.service selene-edu-server.service
    sleep 4
  fi
  curl -sf -m 5 http://127.0.0.1:5001/health >/dev/null \
    && say "5001 healthy" || { say "5001 NOT answering /health"; exit 1; }
else
  say "not LIVE - agents installed, poke.sh inert, servers stay down"
fi
say "ok"
