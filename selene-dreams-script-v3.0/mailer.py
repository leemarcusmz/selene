# =============================================================================
# Selene Dreams — Mailer v1.0 (2026-09-30)
# mailer.py — ONE way to send e-mail from any lane, on any machine
# =============================================================================
#
# WHY THIS EXISTS (Runner Hub p8f). Since the 24 Sep cutover every lane's
# e-mail — reel failure alerts, the educational final-look strip, the monthly
# deep-dive — went through smtplib to smtp.gmail.com:465, and every one of
# them failed silently: DigitalOcean blocks outbound SMTP (25/465/587) from
# the droplet. Marcus's call 30 Sep: Gmail API over HTTPS, no new vendor.
#
# HOW IT WORKS
#   1. Gmail API (preferred). A user OAuth token with the gmail.send scope,
#      stored in token.json.gmail — a SEPARATE file from the Drive token, so
#      neither consent can break the other, and already covered by the
#      .gitignore rule `token.json*`. Same OAuth client (oauth_credentials.json,
#      consent screen "In production", so the refresh token does not expire).
#      Mint it once on a machine with a browser: python3 reauth_gmail.py.
#   2. SMTP fallback. If the Gmail token is absent, fall back to the old
#      app-password path (SELENE_MAIL_FROM / SELENE_MAIL_APP_PASSWORD) — still
#      works from the Mac spare, still fails from the droplet, but now says so.
#
# Every caller gets the same contract: send(...) -> (ok: bool, msg: str) and
# it NEVER raises. Mail is a courtesy channel; a runner must not die over it.
#
# USAGE
#   import mailer
#   ok, msg = mailer.send("[SELENE] subject", "body text",
#                         attachments=[("report.md", data_bytes, "text/markdown")])
#   ok, msg = mailer.send(..., to="someone@example.com")   # default: SELENE_ALERT_TO
#   python3 mailer.py --test                                # send a test mail to yourself
# =============================================================================
# CHANGELOG
#   1.0  2026-09-30  First build. Gmail API + SMTP fallback, shared by
#                    reel_runner 1.20, notify_edu 1.4, deepdive_runner 1.1.
# =============================================================================

import base64
import mimetypes
import os
import sys
from email.message import EmailMessage

VERSION = "1.0"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GMAIL_TOKEN_FILE = os.path.join(BASE_DIR, "token.json.gmail")
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
DEFAULT_TO = "lee.marcusmz@gmail.com"


def _env():
    try:
        import config
        return dict(config._ENV)
    except Exception:
        return {}


def _addresses(env, to):
    sender = (env.get("SELENE_MAIL_FROM") or "").strip()
    to = (to or env.get("SELENE_ALERT_TO") or DEFAULT_TO).strip()
    return sender, to


def _message(subject, body, sender, to, attachments):
    msg = EmailMessage()
    msg["Subject"] = subject
    if sender:
        msg["From"] = sender
    msg["To"] = to
    msg.set_content(body)
    for att in attachments or ():
        filename, data, mime = (list(att) + [None, None])[:3]
        if isinstance(data, str):
            data = data.encode("utf-8")
        if not mime:
            mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        maintype, subtype = mime.split("/", 1)
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return msg


def gmail_credentials(refresh=True):
    """The Gmail token, refreshed and re-saved if needed; None when absent."""
    if not os.path.exists(GMAIL_TOKEN_FILE):
        return None
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_FILE, GMAIL_SCOPES)
    if refresh and not creds.valid:
        creds.refresh(Request())
        with open(GMAIL_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        os.chmod(GMAIL_TOKEN_FILE, 0o600)
    return creds


def _send_gmail(msg):
    from googleapiclient.discovery import build
    creds = gmail_credentials()
    if creds is None:
        return None, "no Gmail token (token.json.gmail) — run reauth_gmail.py"
    svc = build("gmail", "v1", credentials=creds, cache_discovery=False)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    res = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    return True, f"sent via Gmail API (id {res.get('id', '?')})"


def _send_smtp(msg, env):
    import smtplib, ssl
    sender = (env.get("SELENE_MAIL_FROM") or "").strip()
    pw = (env.get("SELENE_MAIL_APP_PASSWORD") or "").replace(" ", "").strip()
    if not sender or not pw:
        return False, "mail not configured (no Gmail token, no SELENE_MAIL_FROM/APP_PASSWORD)"
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20,
                          context=ssl.create_default_context()) as s:
        s.login(sender, pw)
        s.send_message(msg)
    return True, "sent via SMTP fallback"


def send(subject, body, to=None, attachments=None):
    """Send one e-mail. Returns (ok, msg). Never raises."""
    env = _env()
    sender, to = _addresses(env, to)
    try:
        msg = _message(subject, body, sender, to, attachments)
    except Exception as e:
        return False, f"could not build the message ({type(e).__name__}: {str(e)[:120]})"
    try:
        ok, why = _send_gmail(msg)
        if ok:
            return True, f"{why} to {to}"
        gmail_why = why
    except Exception as e:
        gmail_why = f"Gmail API failed ({type(e).__name__}: {str(e)[:160]})"
    try:
        ok, why = _send_smtp(msg, env)
        return ok, (f"{why} to {to} ({gmail_why})" if ok else f"{gmail_why}; {why}")
    except Exception as e:
        why = f"SMTP fallback failed ({type(e).__name__}: {str(e)[:120]})"
        if "unreachable" in str(e).lower() or "timed out" in str(e).lower():
            why += " — outbound SMTP is blocked on the droplet; mint the Gmail token"
        return False, f"{gmail_why}; {why}"


def main():
    if "--test" in sys.argv:
        import socket
        ok, msg = send(f"[SELENE DREAMS] mailer {VERSION} test from {socket.gethostname()}",
                       "If you can read this, the Gmail API path works from this machine.\n"
                       f"\n— mailer {VERSION}")
        print(("OK: " if ok else "FAILED: ") + msg)
        sys.exit(0 if ok else 1)
    creds = gmail_credentials(refresh=False) if os.path.exists(GMAIL_TOKEN_FILE) else None
    print(f"mailer {VERSION} · Gmail token: "
          + ("present" if creds is not None else "absent (SMTP fallback only)"))


if __name__ == "__main__":
    main()
