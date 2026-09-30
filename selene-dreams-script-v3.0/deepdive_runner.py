# =============================================================================
# Selene Dreams — Monthly IG Deep-Dive Runner v1.0 (2026-09-30)
# deepdive_runner.py — the 1st-of-the-month strategic pass, ON THE DROPLET
# =============================================================================
#
# WHY THIS EXISTS. Until 30 Sep 2026 the deep-dive was a cloud scheduled task
# whose prompt carried a GitHub PAT in clear text; when that token died the
# task was disabled (Runner Hub p8e). Marcus's rule: every schedule runs off
# the VPS, tied to nothing else. So this runner does what the cloud task did,
# with the credential that already lives here:
#
#   1. LIVE gate (inert on the spare)          5. verify the report exists
#   2. clone selene-ig-memory (github_token)   6. commit + push (push_with_retry)
#   3. build the prompt from prompts/           7. e-mail the report to Marcus
#      monthly-deepdive.md                         (SELENE_MAIL_* from .env)
#   4. claude -p (stage "deepdive")            8. clean up the clone
#
# The agent never runs git and never sees a token: the runner clones and
# pushes, the agent reads and writes files. Same shape as research_runner.
#
# CLI:
#   python3 deepdive_runner.py                  # month that just ended
#   python3 deepdive_runner.py --month 2026-09  # a specific month
#   python3 deepdive_runner.py --no-push        # dry run: clone kept, nothing
#                                               # pushed, no e-mail
#   python3 deepdive_runner.py --force          # ignore the LIVE gate
# =============================================================================
# CHANGELOG
#   1.0  2026-09-30  First build (replaces the cloud task; Runner Hub p8e).
# =============================================================================

import argparse
import os
import shutil
import sys
import tempfile
from datetime import date, datetime

import config
import pipeline_state
from caption_runner import clone_memory, invoke_claude, load_prompt, log

VERSION = "1.0"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BASE_DIR)
DEEPDIVE = "deepdive"


def previous_month(today=None):
    today = today or date.today()
    y, m = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    return f"{y:04d}-{m:02d}"


def _mail_report(path, month):
    """E-mail the deep-dive to Marcus. Same SMTP setup reel_runner uses
    (SELENE_MAIL_FROM / SELENE_MAIL_APP_PASSWORD / SELENE_ALERT_TO in .env).
    Returns (ok, msg); never raises."""
    try:
        import smtplib
        from email.message import EmailMessage
        env = config._ENV
        sender = (env.get("SELENE_MAIL_FROM") or "").strip()
        pw = (env.get("SELENE_MAIL_APP_PASSWORD") or "").replace(" ", "").strip()
        to = (env.get("SELENE_ALERT_TO") or "lee.marcusmz@gmail.com").strip()
        if not sender or not pw:
            return False, "mail not configured (SELENE_MAIL_FROM/APP_PASSWORD)"
        with open(path, encoding="utf-8") as f:
            body = f.read()
        msg = EmailMessage()
        msg["Subject"] = f"[SELENE DREAMS] Monthly IG deep-dive {month}"
        msg["From"], msg["To"] = sender, to
        msg.set_content(
            f"The {month} deep-dive is in selene-ig-memory at reports/"
            f"{os.path.basename(path)} (also attached).\n\n"
            + body[:6000] + ("\n\n[... full report attached]" if len(body) > 6000 else "")
            + f"\n\n— deepdive_runner {VERSION} on the VPS")
        msg.add_attachment(body.encode("utf-8"), maintype="text", subtype="markdown",
                           filename=os.path.basename(path))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
            s.login(sender, pw)
            s.send_message(msg)
        return True, f"e-mailed to {to}"
    except Exception as e:
        return False, f"e-mail failed ({type(e).__name__}: {str(e)[:100]})"


def run_deepdive(month=None, no_push=False, force=False):
    month = month or previous_month()
    with pipeline_state.stage(DEEPDIVE, week=month) as st:
        return pipeline_state.finish(_run(month, no_push, force), st)


def _run(month, no_push, force):
    if not force and not os.path.exists(os.path.join(REPO_ROOT, "LIVE")):
        return True, "no LIVE file — this machine is not the runner; nothing to do"
    log(f"Monthly deep-dive for {month} (deepdive_runner v{VERSION}"
        + (", NO-PUSH dry run" if no_push else "") + ")...")

    memroot = tempfile.mkdtemp(prefix=f"selene_deepdive_{month}_")
    try:
        mem = clone_memory(memroot)
        if not mem:
            return False, "memory repo clone failed — check github_token.txt"
        reports = [f for f in os.listdir(os.path.join(mem, "reports"))
                   if f.startswith("research-report-")] if os.path.isdir(
                       os.path.join(mem, "reports")) else []
        log(f"  {len(reports)} weekly report(s) in the repo")
        out_file = os.path.join(mem, "reports", f"monthly-deepdive-{month}.md")
        if os.path.exists(out_file) and not force:
            return True, f"monthly-deepdive-{month}.md already exists — nothing to do"

        body, version = load_prompt("monthly-deepdive")
        try:
            prompt = body.format(mem=mem, month=month, out_file=out_file,
                                 today=datetime.now().strftime("%A %Y-%m-%d"))
        except KeyError as e:
            return False, f"prompt placeholder {{{e.args[0]}}} has no value"
        log(f"  running claude (prompt {version}, stage {DEEPDIVE})...")
        ok, msg = invoke_claude(prompt, mem, timeout=3600, stage=DEEPDIVE)
        if not ok:
            return False, f"deep-dive agent failed: {msg}"
        if not os.path.exists(out_file):
            return False, (f"agent finished but wrote no {os.path.basename(out_file)}"
                           f" — see _logs/")
        size = os.path.getsize(out_file)
        log(f"  report written · {size:,} bytes")

        if no_push:
            log(f"  NO-PUSH: clone kept at {mem}; nothing pushed, no e-mail")
            return True, f"dry run complete — report at {out_file}"

        ok2, pmsg = pipeline_state.push_with_retry(
            mem, f"Monthly deep-dive {month}", logger=log)
        log(f"  push: {pmsg}")
        mok, mmsg = _mail_report(out_file, month)
        log(f"  {mmsg}")
        if not ok2:
            return False, f"report written and {mmsg}, but push failed: {pmsg}"
        return True, f"monthly-deepdive-{month}.md pushed · {mmsg}"
    finally:
        if not no_push:
            shutil.rmtree(memroot, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="Selene monthly IG deep-dive")
    ap.add_argument("--month", help="YYYY-MM (default: the month that just ended)")
    ap.add_argument("--no-push", action="store_true",
                    help="dry run: keep the clone, push nothing, send no e-mail")
    ap.add_argument("--force", action="store_true",
                    help="run even without LIVE / even if the report exists")
    a = ap.parse_args()
    ok, msg = run_deepdive(a.month, a.no_push, a.force)
    print(("SUCCESS: " if ok else "FAILED: ") + msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
