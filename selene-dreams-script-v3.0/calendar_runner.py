#!/usr/bin/env python3
"""Social calendar review — evidence instead of guesswork.

Marcus built the promotional calendar by hand and describes it as "still all
just guessing". This runs an agent over it with web access: verifies every
date, looks for moments the category actually acts on, checks what the tracked
competitors really promote around, and flags rows with no basis.

It PROPOSES. It never writes the calendar spreadsheet — the output is a review
plus a ready-to-paste CSV, and a human decides.

Usage:
    python3 calendar_runner.py                 # review this month
    python3 calendar_runner.py --month 2026-09
    python3 calendar_runner.py --dry-run       # show the inputs, call nothing

Cadence: monthly is plenty. The retail calendar does not move week to week,
and the competitor evidence needs time to accumulate before it says anything.
"""
import argparse
import datetime
import os
import shutil
import sys
import tempfile

import pipeline_state
import social_calendar
from caption_runner import clone_memory, invoke_claude, load_prompt, log

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STAGE = "calendar"
TIMEOUT = 2400          # web research over a year of events is not quick


def _calendar_block(events, year):
    if not events:
        return ("The calendar could not be read. Check that the sheet is "
                "shared with the service account, and say in the report that "
                "no rows were available rather than proposing a calendar from "
                "nothing.")
    lines = []
    for e in events:
        span = e["start"].strftime("%b %d")
        if e["end"] != e["start"]:
            span += " - " + e["end"].strftime("%b %d")
        bits = [b for b in (e["type"], e["value"], e["applies"], e["notes"]) if b]
        lines.append(f"- {span} | {e['name']}" +
                     (" | " + " | ".join(bits) if bits else ""))
    return f"{len(events)} row(s) in the {year} tab:\n" + "\n".join(lines)


def run_calendar_review(month=None, dry_run=False):
    month = month or datetime.date.today().strftime("%Y-%m")
    with pipeline_state.stage(STAGE, week=month) as st:
        return pipeline_state.finish(_run(month, dry_run), st)


def _run(month, dry_run):
    year = int(social_calendar.CAL_TAB) if social_calendar.CAL_TAB.isdigit() \
        else datetime.date.today().year

    log(f"Social calendar review for {month}...")
    events = social_calendar.load_events(logger=log)
    log(f"  {len(events)} calendar row(s) read")
    if not events:
        log("  WARNING: no rows. If the sheet is not shared with the service "
            "account the agent has nothing to audit — fix that first.")

    block = _calendar_block(events, year)
    if dry_run:
        print(block)
        return True, "dry run — no agent call made"

    root = tempfile.mkdtemp(prefix=f"selene_calendar_{month}_")
    try:
        mem = clone_memory(root)
        if not mem:
            return False, "memory repo clone failed — the review needs reports/"

        out_report = os.path.join(mem, "reports", f"calendar-review-{month}.md")
        os.makedirs(os.path.dirname(out_report), exist_ok=True)
        prop_dir = os.path.join(mem, "proposals")
        os.makedirs(prop_dir, exist_ok=True)
        out_csv = os.path.join(prop_dir, f"calendar-proposal-{month}.csv")

        body, version = load_prompt("calendar-review")
        prompt = (
            f"TODAY is {datetime.date.today().isoformat()} (Asia/Hong_Kong). "
            f"You have web access — use it, and cite sources.\n\n"
            + body.format(mem=mem, calendar=block, year=year,
                          out_report=out_report, out_csv=out_csv)
        )
        log(f"  invoking agent (prompt {version}) — web research, ~10-30 min")
        ok, msg = invoke_claude(prompt, root, timeout=TIMEOUT, stage="research")
        if not ok:
            return False, f"calendar review failed: {msg}"
        if not os.path.exists(out_report):
            return False, ("agent finished but wrote no review file — see "
                           "_logs/ for the transcript")

        made_csv = os.path.exists(out_csv)
        if not made_csv:
            log("  NOTE: no proposal CSV was written — the review is still "
                "usable, but nothing is ready to paste.")

        pipeline_state.mirror_to_memory(mem)
        import subprocess
        subprocess.run(["git", "-C", mem, "add", "-A"], check=False)
        subprocess.run(["git", "-C", mem, "commit", "-q", "-m",
                        f"Calendar review {month}"], check=False)
        push = subprocess.run(["git", "-C", mem, "push", "-q"], check=False)
        if push.returncode != 0:
            log("  NOTE: push failed — the review exists locally only.")

        return True, (f"Calendar review {month} published"
                      + (" with a proposal CSV" if made_csv else ""))
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", help="YYYY-MM (default: this month)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the calendar the agent would see, then stop")
    a = ap.parse_args()
    ok, msg = run_calendar_review(a.month, a.dry_run)
    print(("OK: " if ok else "FAILED: ") + str(msg))
    sys.exit(0 if ok else 1)
