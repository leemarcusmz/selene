#!/usr/bin/env python3
"""
reauth_drive.py — Selene Dreams · re-authorise the Drive OAuth token
=====================================================================
VERSION 1.0 — 2026-09-15

WHY THIS EXISTS
  token.json (user OAuth, Drive scope) feeds BOTH lanes: v3.0 image generation
  + publish, and the educational lane's library/render/reroll. When Google
  revokes the refresh token ("invalid_grant: Token has been expired or
  revoked") everything that touches Drive stalls silently. This happened
  2026-08-24, 2026-09-08 and 2026-09-15 — a ~7-day cadence, which is the
  refresh-token lifetime for an OAuth consent screen still in "Testing".
  The permanent fix is publishing the consent screen (Cloud project
  "selene-dreams" → APIs & Services → OAuth consent screen → Publish app);
  this script is the one-command re-auth to run after that (and any time the
  token dies again).

USAGE (macOS Terminal, NOT headless — it opens a browser consent window)
  cd ".../selene-dreams-script-v3.0"
  python3 reauth_drive.py            # re-auth: backs up the dead token, opens browser, verifies
  python3 reauth_drive.py --check    # read-only: is the current token alive? exit 0 yes / 1 no

AFTER A SUCCESSFUL RE-AUTH
  Run "Start Selene AI" so server.py and edu_server.py pick up the new token
  (Python caches credentials per process). Then re-fire any stuck rows.

CHANGELOG
  1.0  2026-09-15  First version. --check mode, dated backup of the old
                   token, interactive InstalledAppFlow, post-auth verification
                   via drive.about().get(), prints the account it authorised.
"""
import os, sys, shutil, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE); sys.path.insert(0, HERE)
import config  # noqa: E402

TOKEN  = config.OAUTH_TOKEN_FILE
SECRET = config.OAUTH_CREDENTIALS_FILE
SCOPES = ["https://www.googleapis.com/auth/drive"]


def _verify(creds):
    from googleapiclient.discovery import build
    about = build("drive", "v3", credentials=creds).about().get(fields="user(emailAddress)").execute()
    return about["user"]["emailAddress"]


def check():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    if not os.path.exists(TOKEN):
        print("NO TOKEN — token.json missing"); return 1
    try:
        creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)
        if not creds.valid:
            creds.refresh(Request())
            with open(TOKEN, "w") as f: f.write(creds.to_json())
        print(f"ALIVE — Drive token OK for {_verify(creds)}"); return 0
    except Exception as e:
        print(f"DEAD — {e}"); return 1


def reauth():
    from google_auth_oauthlib.flow import InstalledAppFlow
    if os.path.exists(TOKEN):
        bak = TOKEN + ".dead-" + datetime.datetime.now().strftime("%Y%m%d-%H%M")
        shutil.move(TOKEN, bak)
        print(f"old token moved to {os.path.basename(bak)}")
    flow = InstalledAppFlow.from_client_secrets_file(SECRET, SCOPES)
    # access_type=offline + prompt=consent guarantees a NEW refresh token is issued
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    with open(TOKEN, "w") as f: f.write(creds.to_json())
    os.chmod(TOKEN, 0o600)
    email = _verify(creds)
    print(f"OK — new token written, authorised as {email}")
    print("NEXT: run 'Start Selene AI' so both servers reload the token.")
    return 0


if __name__ == "__main__":
    sys.exit(check() if "--check" in sys.argv else reauth())
