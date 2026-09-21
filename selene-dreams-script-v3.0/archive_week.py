# =============================================================================
# Selene Dreams — Candidate Image Archive v1.0 (2026-08-13)
# archive_week.py — Save a week's candidate images before the CDN forgets them
# =============================================================================
#
# WHY: Instagram CDN URLs expire within days. Scores, attributes and human
# picks all survive in the repo, but the images they refer to rot — which is
# what made the first eval run unscoreable (11 candidates, 11 x HTTP 403).
#
# screen_runner.py now archives images as it screens. This utility does the
# same job for a week that was screened before that existed, or whenever a
# screening ran on a stale process. It touches nothing else: no re-scoring, no
# shortlist changes, no disruption to an invite that may already be out.
#
#   python3 archive_week.py --week 2026-08-10
#   python3 archive_week.py --week 2026-08-10 --dry-run
# =============================================================================

import argparse
import json
import os
import shutil
import sys
import tempfile

import pipeline_state
from caption_runner import clone_memory, log
from screen_runner import download_hero, archive_hero


def archive_week(week, dry_run=False):
    workdir = tempfile.mkdtemp(prefix=f"selene_archive_{week}_")
    try:
        mem = clone_memory(workdir)
        if not mem:
            return False, "memory repo clone failed"

        # Prefer the candidates file: it holds every candidate, kept and cut,
        # and the cuts are what give the eval set its contrast.
        cand_path = os.path.join(mem, "candidates", f"candidates-{week}.json")
        src = "candidates"
        if not os.path.exists(cand_path):
            cand_path = os.path.join(mem, "shortlists", f"shortlist-{week}.json")
            src = "shortlist"
            if not os.path.exists(cand_path):
                return False, f"no candidates or shortlist file for {week}"

        with open(cand_path) as f:
            entries = json.load(f).get("entries", [])
        if not entries:
            return False, f"{src} file for {week} has no entries"

        dest_dir = os.path.join(mem, "candidate-images", week)
        already = (len(os.listdir(dest_dir))
                   if os.path.isdir(dest_dir) else 0)
        log(f"  {len(entries)} entr(ies) from {src}; {already} already archived")

        tmp_imgs = os.path.join(workdir, "imgs")
        os.makedirs(tmp_imgs, exist_ok=True)

        saved, skipped, failed = 0, 0, []
        for e in entries:
            n = e.get("n")
            imgs = e.get("images") or []
            if not imgs:
                failed.append(f"#{n} (no image URL)")
                continue
            if os.path.exists(os.path.join(dest_dir, f"cand_{n}.jpg")):
                skipped += 1
                continue
            if dry_run:
                saved += 1
                continue
            tmp = os.path.join(tmp_imgs, f"cand_{n}.jpg")
            if download_hero(imgs[0], tmp) and archive_hero(tmp, mem, week, n):
                saved += 1
            else:
                failed.append(f"#{n} (CDN link dead)")

        if dry_run:
            return True, (f"would archive {saved}, skip {skipped} already "
                          f"present, {len(failed)} unavailable")
        if saved == 0:
            return False, (f"archived nothing — {len(failed)} link(s) already "
                           f"expired. Nothing to be done for this week; future "
                           f"weeks archive as they are screened.")

        pipeline_state.mirror_to_memory(mem)
        ok, msg = pipeline_state.push_with_retry(
            mem, f"Archive candidate images {week}", logger=log)
        if not ok:
            return False, f"archived {saved} but push failed: {msg}"

        out = f"archived {saved} image(s) for {week}"
        if skipped:
            out += f" · {skipped} already present"
        if failed:
            out += f" · {len(failed)} unavailable: {', '.join(failed[:6])}"
        return True, out
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="Archive a week's candidate images")
    ap.add_argument("--week", required=True, help="e.g. 2026-08-10")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be archived, download nothing")
    args = ap.parse_args()
    ok, msg = archive_week(args.week, args.dry_run)
    print(("SUCCESS: " if ok else "FAILED: ") + msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
