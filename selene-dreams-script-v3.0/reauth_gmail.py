#!/usr/bin/env python3
"""
reauth_gmail.py — Selene Dreams · mint or renew the Gmail-send OAuth token
==========================================================================
VERSION 1.0 — 2026-09-30

WHY THIS EXISTS
  mailer.py sends through the Gmail API because the droplet cannot reach any
  SMTP port (Runner Hub p8f). The API needs a user OAuth token with the
  gmail.send scope. It lives in token.json.gmail — deliberately SEPARATE from
  token.json (Drive), so re-consenting one can never break the other. Same
  OAuth client (oauth_credentials.json); the consent screen is "In production",
  so the refresh token does not expire on the 7-day Testing clock.

USAGE (a machine WITH a browser — the MacBook; the droplet has none)
  cd ".../selene-dreams-script-v3.0"
  python3 reauth_gmail.py            # opens the consent window, writes token.json.gmail, verifies
  python3 reauth_gmail.py --check    # read-only: is the token alive? exit 0 yes / 1 no

THEN copy it to the runner (it is gitignored by `token.json*`, never commit):
  scp token.json.gmail vps:~/runner/selene/selene-dreams-script-v3.0/
  ssh vps 'cd ~/runner/selene/selene-dreams-script-v3.0 && ../.venv/bin/python mailer.py --test'

CHANGELOG
  1.0  2026-09-30  First version, modelled on reauth_drive.py 1.0. Verification is
                   refresh + scope check: getProfile needs a read scope this
                   token deliberately does not have (learned on first run).
"""
import datetime
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)
import config  # noqa: E402
import mailer  # noqa: E402

TOKEN = mailer.GMAIL_TOKEN_FILE
SECRET = config.OAUTH_CREDENTIALS_FILE
SCOPES = mailer.GMAIL_SCOPES


def _verify(creds):
    """gmail.send alone cannot call users.getProfile (that needs a read
    scope), so 'verified' here means: the token refreshes and carries the
    send scope. The real proof is `python3 mailer.py --test`."""
    from google.auth.transport.requests import Request
    creds.refresh(Request())
    scopes = set(creds.scopes or [])
    if not scopes & set(SCOPES):
        raise RuntimeError(f"token lacks gmail.send (has {sorted(scopes)})")
    return "send scope present, refresh OK — run `python3 mailer.py --test` to prove delivery"


def check():
    if not os.path.exists(TOKEN):
        print("NO TOKEN — token.json.gmail missing")
        return 1
    try:
        creds = mailer.gmail_credentials()
        print(f"ALIVE — {_verify(creds)}")
        return 0
    except Exception as e:
        print(f"DEAD — {type(e).__name__}: {str(e)[:200]}")
        return 1


def reauth():
    from google_auth_oauthlib.flow import InstalledAppFlow
    if not os.path.exists(SECRET):
        sys.exit(f"oauth_credentials.json not found at {SECRET}")
    if os.path.exists(TOKEN):
        bak = f"{TOKEN}.dead-{datetime.datetime.now():%Y%m%d-%H%M%S}"
        shutil.move(TOKEN, bak)
        print(f"old token moved to {os.path.basename(bak)}")
    flow = InstalledAppFlow.from_client_secrets_file(SECRET, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    with open(TOKEN, "w") as f:
        f.write(creds.to_json())
    os.chmod(TOKEN, 0o600)
    print(f"token.json.gmail written · {_verify(creds)}")
    print("next: scp token.json.gmail vps:~/runner/selene/selene-dreams-script-v3.0/")
    return 0


if __name__ == "__main__":
    sys.exit(check() if "--check" in sys.argv else reauth())
