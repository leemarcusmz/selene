# =============================================================================
# Selene Dreams — Weekly Research Runner v2.1.1 (2026-09-30)
# research_runner.py — Run the Monday IG research locally, in phases
# =============================================================================
# CHANGELOG
#   2.1.1 2026-09-30 Phase 3 gets the same exclude list + account rotation
#                    (research-p3 v2). The v2.1 dry run for 2026-09-28 proved
#                    the rules hold (pool clean, nothing to enforce) but left
#                    only 10 candidates, 1 from a fresh account: phase 3 had
#                    fetched images for 35 of ~173 posts and 23 of those were
#                    already spent. The memory clone now happens before phase
#                    3 so the longlist can skip spent posts and go wide on
#                    fresh accounts.
#   2.1  2026-09-30  RESEARCH LANE v2.1 — the pool stops repeating itself.
#                    Diagnosis (shortlists 24 Aug-28 Sep): already-offered and
#                    already-PICKED posts came back week after week
#                    (DcCN9qWj7Gy picked 4x), the same 4-5 accounts dominated,
#                    and phase 4 never saw taste/brief.md. Now:
#                    (a) research_pool.history() reads every earlier
#                        candidates/shortlist file + every PICKED line and
#                        hands phase 4 a HARD EXCLUDE list ({exclude_block})
#                        and the account rotation ({accounts_block});
#                    (b) {taste_brief} (taste_brief.brief_block("research"))
#                        is injected into research-p4 v7 like every writer;
#                    (c) after phase 4 the runner ENFORCES the rules on the
#                        published candidates file — drops excluded posts,
#                        caps 2 per account, tags account/freshAccount — and
#                        pushes the corrected file if anything changed. The
#                        prompt asks; the code guarantees.
#                    (d) --no-push: dry run for a proof — phase 4 writes into
#                        the clone but nothing is committed; the clone is
#                        kept and its path printed. {publish_instruction}
#                        carries the difference into the prompt.
#   2.0  2026-08-13  Phased runner (see WHY v2 below).
#
# WHY v2: v1 handed the agent one enormous instruction that included
# "sleep 950" between same-path Apify calls. That is unexecutable — Claude
# Code's Bash tool caps at 600s — so the agent did the only sensible thing:
# it announced "waiting for the API cooldown" and ended its turn. In headless
# `-p` mode, ending the turn ends the process. Both failed runs (2026-08-12
# 23:09 and 2026-08-13 13:54) died exactly there, having done real work that
# was then thrown away.
#
# THE FIX: the runner owns the waiting, the agent owns the thinking. Four
# short phases, each ending in a file on disk:
#
#   Phase 1  pull posts + stats + hashtags        -> step1-raw.md
#   ... runner sleeps (same-path API spacing) ...
#   Phase 2  captions + comment mining            -> step2-captions-comments.md
#   ... runner sleeps ...
#   Phase 3  image URLs for the candidate pool    -> step3-images.md
#   Phase 4  analyse, critic pass, write memory   -> report + candidates in repo
#
# Three things this buys beyond just working: a crashed phase can be rerun
# without repeating the ones before it (the files persist); each phase is a
# small, checkable artifact instead of an hour of hidden context; and the
# expensive API calls happen once, early, so a failure in analysis costs
# nothing to retry.
#
# CLI usage:
#   python3 research_runner.py                 # current week, full spacing
#   python3 research_runner.py --spacing 60    # faster, for testing
#   python3 research_runner.py --from-phase 4  # reuse existing phase files
#   python3 research_runner.py --week 2026-08-10
#   python3 research_runner.py --from-phase 4 --week 2026-09-28 --no-push   # proof, nothing pushed
# =============================================================================

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timedelta

import config
import pipeline_state
import research_pool
from caption_runner import clone_memory, invoke_claude, load_prompt, log
import social_calendar

VERSION = "2.1.1"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_ROOT = os.path.join(BASE_DIR, "_research")

# Same-path Apify calls need spacing or the CDN serves a stale cached body.
# The cb= cache-buster covers most of it; this is the belt to that braces.
DEFAULT_SPACING = 950


def monday_of_current_week():
    today = datetime.now().date()
    return today - timedelta(days=today.weekday())


def candidates_exist(week, token):
    url = ("https://api.github.com/repos/leemarcusmz/selene-ig-memory/"
           f"contents/candidates/candidates-{week}.json")
    req = urllib.request.Request(url, headers={
        "Authorization": "token " + token,
        "Accept": "application/vnd.github+json"})
    try:
        urllib.request.urlopen(req, timeout=30)
        return True
    except Exception:
        return False


def _run_phase(name, prompt_file, workdir, out_file, week, extra=None,
               timeout=1800):
    """One phase = one agent call that must end in a file on disk."""
    common, common_v = load_prompt("research-common")
    body, version = load_prompt(prompt_file)
    fields = {"out_file": out_file, "week": week,
              # Secrets live in .env (via config) and are substituted here at
              # runtime, so the prompt FILES carry no credentials.
              "apify_token": config.APIFY_TOKEN,
              "apify_run_token": config.APIFY_RUN_TOKEN}
    fields.update(extra or {})
    try:
        common = common.format(**fields)
        body = body.format(**fields)
    except KeyError as e:
        # A prompt edit added a placeholder nothing supplies. Fail with the
        # name instead of a stack trace — added 2026-08-19 after {calendar}
        # made this class of mistake easy.
        return False, (f"{name}: prompt placeholder {{{e.args[0]}}} has no "
                       f"value — fix the prompt file or pass it in fields")
    prompt = (
        f"TODAY is {datetime.now().strftime('%A %Y-%m-%d %H:%M')} local time "
        f"(Asia/Hong_Kong). The research week is {week} — use {week} in every "
        f"file name. Work from {BASE_DIR}; github_token.txt is there.\n\n"
        + common + "\n\n" + body
    )
    log(f"  [{name}] running (prompt {version}, common {common_v})...")
    # Publish the sub-phase so /state (and the dashboard reading it) can show
    # "phase 2 of 4 · captions" instead of an hour of undifferentiated
    # "started". name looks like "phase 2/4 · captions+comments".
    try:
        step = total = None
        head = name.split("\u00b7")[0].strip()          # "phase 2/4"
        if "/" in head:
            a, b = head.split()[-1].split("/")
            step, total = int(a), int(b)
        pipeline_state.note_phase(pipeline_state.RESEARCH, week, name,
                                  step=step, total=total)
    except Exception:
        pass
    t0 = time.time()
    ok, msg = invoke_claude(prompt, workdir, timeout=timeout, stage="research")
    took = time.time() - t0
    if not ok:
        return False, f"{name} failed after {took:.0f}s: {msg}"
    if out_file and not os.path.exists(out_file):
        return False, (f"{name} finished after {took:.0f}s but wrote no "
                       f"{os.path.basename(out_file)} — see _logs/")
    size = os.path.getsize(out_file) if out_file else 0
    log(f"  [{name}] done in {took:.0f}s"
        + (f" · {size:,} bytes written" if size else ""))
    return True, "ok"


def _sleep(seconds, why):
    if seconds <= 0:
        return
    log(f"  waiting {seconds}s — {why} (the runner waits, not the agent)")
    time.sleep(seconds)


def run_research(week=None, spacing=DEFAULT_SPACING, from_phase=1,
                 no_push=False):
    week = week or monday_of_current_week().isoformat()
    with pipeline_state.stage(pipeline_state.RESEARCH, week=week) as st:
        return pipeline_state.finish(
            _run_research(week, spacing, from_phase, no_push), st)


PUBLISH_LIVE = ('Then: `git add -A && git commit -m "Weekly research {week}" '
                '&& git push` (one retry; report failure honestly).')
PUBLISH_DRY = ("DRY RUN: write every file exactly as described, but do NOT "
               "run git add, git commit or git push — leave the working tree "
               "dirty. The runner inspects the files in place.")


def _taste_brief_block():
    try:
        import taste_brief
        return taste_brief.brief_block("research")
    except Exception as e:
        log(f"  taste brief unavailable ({type(e).__name__}) — phase 4 runs "
            f"without it")
        return "(taste brief unavailable this run)"


def _enforce_pool(mem, week, hist):
    """Re-apply the v2.1 rules to what phase 4 actually published.
    Returns (changed, report_lines)."""
    path = os.path.join(mem, "candidates", f"candidates-{week}.json")
    if not os.path.exists(path):
        return False, [f"no candidates-{week}.json in the clone — nothing to enforce"]
    with open(path) as f:
        data = json.load(f)
    before = data.get("entries") or []
    kept, report = research_pool.enforce(before, hist)
    lines = research_pool.report_lines(report)
    changed = json.dumps(kept, sort_keys=True) != json.dumps(before, sort_keys=True)
    if changed:
        data["entries"] = kept
        data["hygiene"] = {"version": research_pool.VERSION, "week": week,
                           "enforced": datetime.now().isoformat(timespec="seconds"),
                           "dropped": report["dropped"]}
        with open(path, "w") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
    return changed, lines


def _run_research(week, spacing, from_phase, no_push=False):
    log(f"Weekly research for week {week} (local, phased, runner v{VERSION}"
        + (", NO-PUSH dry run" if no_push else "") + ")...")

    with open(os.path.join(BASE_DIR, "github_token.txt")) as f:
        token = f.read().strip()
    if candidates_exist(week, token) and from_phase == 1:
        return True, f"candidates-{week}.json already exists — research already ran"

    workdir = os.path.join(WORK_ROOT, week)
    os.makedirs(workdir, exist_ok=True)
    step1 = os.path.join(workdir, "step1-raw.md")
    step2 = os.path.join(workdir, "step2-captions-comments.md")
    step3 = os.path.join(workdir, "step3-images.md")

    # ---- Phase 1: the week's raw data -------------------------------------
    if from_phase <= 1:
        ok, msg = _run_phase("phase 1/4 · data", "research-p1", workdir,
                             step1, week)
        if not ok:
            return False, msg
        _sleep(spacing, "same-path Apify spacing before the captions call")
    elif not os.path.exists(step1):
        return False, f"--from-phase {from_phase} but {step1} is missing"

    # ---- Phase 2: captions + comment mining -------------------------------
    if from_phase <= 2:
        ok, msg = _run_phase("phase 2/4 · captions+comments", "research-p2",
                             workdir, step2, week, {"step1_file": step1})
        if not ok:
            return False, msg
        _sleep(spacing, "same-path Apify spacing before the images call")

    # ---- Memory clone (v2.1.1: before phase 3, so the longlist knows what is
    # already spent) ---------------------------------------------------------
    memroot = tempfile.mkdtemp(prefix=f"selene_research_{week}_")
    try:
        mem = clone_memory(memroot)
        if not mem:
            return False, ("memory repo clone failed — phases 3 and 4 need "
                           "the offered/picked history, brand-guide.md and "
                           "somewhere to publish")
        # v2.1: what has already been offered or picked, and which accounts
        # are fresh. Read from the clone, so it is exactly what the repo says.
        hist = research_pool.history(mem, week)
        log(f"  hygiene: {len(hist['offered'])} posts offered before, "
            f"{len(hist['picked'])} picked, {len(hist['recent_accounts'])} "
            f"account(s) offered in the last {research_pool.FRESH_WEEKS} weeks "
            f"({len(hist['weeks'])} earlier week(s) read)")
        exclude_block = research_pool.exclude_block(hist)
        accounts_block = research_pool.accounts_block(hist, week)

        # ---- Phase 3: image URLs ------------------------------------------
        if from_phase <= 3:
            ok, msg = _run_phase("phase 3/4 · images", "research-p3", workdir,
                                 step3, week, {"step1_file": step1,
                                               "exclude_block": exclude_block,
                                               "accounts_block": accounts_block})
            if not ok:
                return False, msg

        for path in (step2, step3):
            if not os.path.exists(path):
                log(f"  NOTE: {os.path.basename(path)} missing — phase 4 will "
                    f"work without it and should say so in the report.")

        # ---- Phase 4: analyse, criticise, publish -------------------------
        # Upcoming promotions steer the PRODUCT mapping (pick linen references
        # while a linen promo is three weeks out), never the caption voice —
        # discount urgency is explicitly off-brand. Degrades to a plain "no
        # promotions / could not read" sentence if the sheet is unreachable.
        calendar_block = social_calendar.as_prompt_block(logger=log)
        ok, msg = _run_phase(
            "phase 4/4 · report", "research-p4", workdir, None, week,
            {"step1_file": step1, "step2_file": step2, "step3_file": step3,
             "mem": mem, "calendar": calendar_block,
             "taste_brief": _taste_brief_block(),
             "exclude_block": exclude_block,
             "accounts_block": accounts_block,
             "publish_instruction": (PUBLISH_DRY if no_push
                                     else PUBLISH_LIVE.format(week=week))},
            timeout=3600)
        if not ok:
            return False, msg
        # v2.1: enforce. The agent was told; the code checks.
        changed, lines = _enforce_pool(mem, week, hist)
        for ln in lines:
            log("  hygiene: " + ln)
        if no_push:
            log(f"  NO-PUSH: clone kept at {mem} — inspect candidates/"
                f"candidates-{week}.json and reports/ there; nothing was "
                f"committed or pushed.")
            return True, (f"dry run complete for {week}; "
                          + (f"enforcement corrected the pool: {lines[0]}"
                             if changed else f"pool clean as written: {lines[0]}")
                          + f" — files at {mem}")
        if changed:
            ok2, pmsg = pipeline_state.push_with_retry(
                mem, f"Research hygiene {week}: enforce v2.1 pool rules",
                logger=log)
            log(f"  hygiene push: {pmsg}" if ok2
                else f"  WARNING: hygiene push failed ({pmsg}) — the repo "
                     f"still holds the un-enforced pool")
    finally:
        if not no_push:
            shutil.rmtree(memroot, ignore_errors=True)

    if candidates_exist(week, token):
        log("  candidates file confirmed in repo — screener + invite follow.")
        return True, f"Research complete; candidates-{week}.json published"

    return False, (f"phase 4 finished but candidates-{week}.json is not in the "
                   f"repo. Phase files are kept at {workdir} — rerun just the "
                   f"analysis with: python3 research_runner.py --from-phase 4")


def main():
    ap = argparse.ArgumentParser(description="Selene weekly research runner")
    ap.add_argument("--week", help="YYYY-MM-DD (Monday). Default: this week")
    ap.add_argument("--spacing", type=int, default=DEFAULT_SPACING,
                    help="seconds between same-path Apify calls "
                         f"(default {DEFAULT_SPACING}; lower risks stale data)")
    ap.add_argument("--from-phase", type=int, default=1, choices=[1, 2, 3, 4],
                    help="resume from a phase, reusing existing phase files")
    ap.add_argument("--no-push", action="store_true",
                    help="dry run: phase 4 writes into the clone, nothing is "
                         "committed or pushed, the clone is kept (v2.1)")
    args = ap.parse_args()

    ok, msg = run_research(args.week, args.spacing, args.from_phase,
                           args.no_push)
    print(("SUCCESS: " if ok else "FAILED: ") + msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
