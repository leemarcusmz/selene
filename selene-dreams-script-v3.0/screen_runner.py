# =============================================================================
# Selene Dreams — Visual Screening Runner v1.3 (2026-09-16)
# screen_runner.py — Give the weekly research agent eyes + a taste that learns
# =============================================================================
#
# The cloud research agent cannot view Instagram/Pinterest images (CDN is
# blocked in its environment), so on Mondays it publishes a WIDE candidate
# pool (candidates/candidates-YYYY-MM-DD.json in selene-ig-memory) instead of
# a final shortlist. The Apps Script poller then POSTs /screen to this Mac,
# and this runner:
#
#   1. Pulls the candidates file + brand-guide.md + visual-taste.md +
#      selections.md from the memory repo.
#   2. Downloads each candidate's hero image and VIEWS it with the Claude
#      Code CLI, scoring it against the brand's 12-point image rubric —
#      informed by past weeks' scores vs what the team actually picked
#      (the learning loop).
#   3. Writes the top candidates as shortlists/shortlist-YYYY-MM-DD.json
#      (same schema the picker + invite email already consume — downstream
#      flow unchanged), each entry annotated with its brandScore + rationale.
#   4. Appends a screening log + any new taste learnings to visual-taste.md,
#      commits and pushes.
#
# CLI usage:
#   python3 screen_runner.py --week 2026-08-17
# =============================================================================
# CHANGELOG
#   1.3  2026-09-16  THE TASTE BRIEF. Runs taste_brief.maybe_distill() first
#                    (weekly, Monday, before scoring) and passes {taste_brief}
#                    into screening.md v5. Fail-open.
#   1.2  2026-09-16  MARCUS'S REFERENCES CALIBRATE THE SCREENER. The screener
#                    learned only from picks (selections.md); now it also
#                    views the newest images from Drive "02. Reference
#                    Images / 01. Style" (reference_drive) before scoring,
#                    as {reference_section} in screening.md v4. Fail-open.
#   1.1  2026-08-31  TOP-UP ARCHIVE INTEGRITY. Three separate faults let the
#                    picker publish rows whose images could never load:
#                    (a) POINTER CLOBBER — a carried entry that was ITSELF
#                        carried had its inherited archiveWeek overwritten with
#                        the intermediate week, pointing at a folder that never
#                        held its images. Week 2026-08-31 entry #5 pointed at
#                        2026-08-24; its six slides were sitting in 2026-08-17
#                        the whole time. archiveWeek is now INHERITED.
#                    (b) WEAK GUARD — eligibility checked only that the week's
#                        image DIRECTORY existed, not that this entry's slides
#                        were in it. Every slide file is now verified; an
#                        entry is TRIMMED to its contiguous archived prefix
#                        (a proven high scorer is worth keeping cover-only)
#                        and skipped outright only when even the cover is
#                        missing. Both outcomes are logged with the reason.
#                    (c) Weeks before 2026-08-17 archived covers only (the
#                        all-slides pass did not exist yet), so multi-slide
#                        entries carried from them are unrecoverable. (b)
#                        trims them to their cover instead of shipping rows
#                        of empty boxes.
#                    Archive gaps now also surface in the stage message, so
#                    they reach runs.jsonl and the dashboard instead of dying
#                    in launchd stdout.
#   1.0  2026-08-12  First build.
# =============================================================================

import argparse
import json
import re
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime

import csv

import memory_digests
import pipeline_state
from caption_runner import clone_memory, invoke_claude_json, load_prompt, log

SCREEN_SCHEMA = {
    "scores": {"type": "list", "min_len": 1},
    "learnings": {"type": "str", "required": False},
}

ATTR_CSV = "screening-attributes.csv"
ATTR_HEADER = ["date", "week", "n", "source", "type", "score", "kept",
               "postUrl",
               "setting", "timeOfDay", "palette", "humanPresence", "crop",
               "textOverlay", "styling", "engagement"]

SHORTLIST_SIZE_MIN = 8
# Top-up (2026-08-17): a thin week is backfilled from references that already
# cleared a HIGHER bar in an earlier week and were never used, rather than by
# lowering this week's bar. On 2026-08-17 only 2 of 17 candidates were on
# brand; padding to 8 would have meant shipping a resort scene and a UGC
# snapshot. Carried entries keep their own week so their archived images
# still resolve — see the origN/archiveWeek note in picker.gs.
TOPUP_MIN_SCORE = 8          # strictly better than MIN_SCORE — proven leftovers
TOPUP_MAX_AGE_WEEKS = 6      # older than this and the aesthetic has moved on
SHORTLIST_SIZE_MAX = 12
MIN_SCORE = 7          # rubric: 7-9 acceptable, 10-12 strong

def gh_fetch_json(path, token):
    url = f"https://api.github.com/repos/leemarcusmz/selene-ig-memory/contents/{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": "token " + token,
        "Accept": "application/vnd.github.raw+json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def _worth_retrying(e):
    """403/404 from a CDN means the link is dead, not busy — retrying an
    expired Instagram URL just wastes six seconds per candidate."""
    if isinstance(e, urllib.error.HTTPError) and e.code in (
            400, 401, 403, 404, 410):
        return False
    return True


def download_hero(url, dest):
    def _get():
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    try:
        data = pipeline_state.retry(_get, label="hero download", logger=log,
                                    retry_if=_worth_retrying)
        with open(dest, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        log(f"    hero download failed: {e}")
        return False


def archive_slide(src, mem_dir, week, n, i):
    """Archive slide i of candidate n (i=1 is the cover)."""
    return _archive(src, mem_dir, week,
                    f"cand_{n}.jpg" if i == 1 else f"cand_{n}_s{i}.jpg")


def archive_hero(src, mem_dir, week, n):
    """Keep a small copy of every candidate image inside the memory repo.

    Instagram CDN URLs expire within days, so a shortlist recorded in July is
    unscoreable by August — which is exactly what broke the first eval run.
    The scores, the attributes and the human's picks all survive; only the
    images rot. Archiving a downscaled copy at screening time makes the
    evidence durable, so the eval set keeps working as it grows.
    """
    return _archive(src, mem_dir, week, f"cand_{n}.jpg")


def _archive(src, mem_dir, week, filename):
    try:
        dest_dir = os.path.join(mem_dir, "candidate-images", week)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, filename)
        try:
            from PIL import Image
            im = Image.open(src)
            im.thumbnail((640, 640))
            im.convert("RGB").save(dest, "JPEG", quality=65, optimize=True)
        except ImportError:
            # No Pillow — keep the original only if it is small enough that a
            # year of them will not bloat the repo.
            if os.path.getsize(src) <= 250_000:
                shutil.copy(src, dest)
            else:
                return False
        return True
    except Exception as e:
        log(f"    NOTE: could not archive {filename}: {e}")
        return False


def _used_reference_urls(mem):
    """Every reference already turned into prompts — the local pipeline state
    records the referenceUrl per queue row, which is the cheapest reliable
    record of what has actually been used."""
    used = set()
    try:
        st = pipeline_state.load_state()
        for row in (st.get("rows") or {}).values():
            url = ((row.get("prompts") or {}).get("referenceUrl") or "").strip()
            if url:
                used.add(url)
    except Exception:
        pass
    # prompt-playbook.md is the durable second source, in case state was reset.
    try:
        with open(os.path.join(mem, "prompt-playbook.md")) as f:
            for m in re.finditer(r"https://www\.instagram\.com/p/[A-Za-z0-9_-]+/?",
                                 f.read()):
                used.add(m.group(0))
    except Exception:
        pass
    return used


def _slide_filename(n, i):
    """Archived name for slide i of candidate n. i=1 is the cover."""
    return f"cand_{n}.jpg" if i == 1 else f"cand_{n}_s{i}.jpg"


def _archive_gaps(mem, archive_week, orig_n, image_count):
    """Which of this entry's slides are NOT in the archive.

    The picker renders live Instagram CDN URLs and falls back to the archived
    copy when one 404s. That fallback is the ONLY thing standing between a
    weeks-old carried entry and a row of empty boxes, so "the archive has this
    entry" has to mean every slide, not just the folder existing.
    """
    missing = []
    base = os.path.join(mem, "candidate-images", archive_week)
    for i in range(1, max(1, int(image_count or 1)) + 1):
        if not os.path.exists(os.path.join(base, _slide_filename(orig_n, i))):
            missing.append(i)
    return missing


def _top_up(shortlist, mem, week):
    """Backfill a thin shortlist from earlier weeks' unused high scorers.

    Same bar, not a lower one: only entries that scored TOPUP_MIN_SCORE or
    better, that nobody turned into prompts, and whose images were archived
    under their own week. Returns how many were added.
    """
    try:
        sl_dir = os.path.join(mem, "shortlists")
        if not os.path.isdir(sl_dir):
            return 0
        have = {e.get("postUrl") for e in shortlist["entries"]}
        used = _used_reference_urls(mem)

        weeks = []
        for fn in os.listdir(sl_dir):
            m = re.match(r"^shortlist-(\d{4}-\d{2}-\d{2})\.json$", fn)
            if m and m.group(1) != week:
                weeks.append(m.group(1))
        weeks.sort(reverse=True)
        weeks = weeks[:TOPUP_MAX_AGE_WEEKS]

        pool = []
        skipped = []
        trimmed = []
        for wk in weeks:
            try:
                with open(os.path.join(sl_dir, f"shortlist-{wk}.json")) as f:
                    prev = json.load(f)
            except Exception:
                continue
            for e in prev.get("entries", []):
                url = e.get("postUrl")
                if not url or url in have or url in used:
                    continue
                try:
                    score = float(e.get("brandScore") or 0)
                except (TypeError, ValueError):
                    score = 0
                if score < TOPUP_MIN_SCORE:
                    continue
                # Its images live under ITS week, not this one — and if
                # this entry was ALREADY a carried one, under the week it
                # first came from. Overwriting that inherited pointer with wk
                # is what broke week 2026-08-31 entry #5.
                aw = e.get("archiveWeek") or wk
                orig_n = e.get("origN", e.get("n"))
                imgs = list(e.get("images") or [])
                gaps = _archive_gaps(mem, aw, orig_n, len(imgs))
                if gaps:
                    # TRIM, don't drop. A carried entry already cleared a
                    # higher bar than this week's, and the pool is thin by
                    # definition whenever top-up runs at all — throwing away a
                    # proven 9 because slide 4 is missing costs more than it
                    # saves. Keep the CONTIGUOUS archived prefix: the picker
                    # resolves an archived slide by its display index, so a
                    # non-contiguous subset would renumber the survivors and
                    # point every one of them at the wrong file.
                    keep_n = min(gaps) - 1
                    if keep_n < 1:
                        skipped.append(
                            f"{e.get('source', '?')} cand_{orig_n} from {aw} "
                            f"(no archived cover)")
                        continue
                    trimmed.append(
                        f"{e.get('source', '?')} cand_{orig_n} from {aw} "
                        f"({len(imgs)} slides -> {keep_n})")
                    imgs = imgs[:keep_n]
                ne = dict(e)
                ne["images"] = imgs
                ne["archiveWeek"] = aw
                ne["carriedFrom"] = wk
                ne["_score"] = score
                pool.append(ne)
                have.add(url)

        # Best first; newest first on a tie — a 9 from last week beats a 9 from
        # five weeks ago. Two passes because Python's sort is stable: order by
        # recency, then by score, and the recency order survives within a score.
        pool.sort(key=lambda e: e["carriedFrom"], reverse=True)
        pool.sort(key=lambda e: -e["_score"])

        if trimmed:
            log(f"  top-up trimmed {len(trimmed)} reference(s) to their "
                f"archived slides: " + "; ".join(trimmed))
        if skipped:
            # Loud on purpose: these are silently-unusable references, and the
            # pool shrinking is the visible symptom of an archiving failure
            # weeks earlier.
            log(f"  top-up skipped {len(skipped)} reference(s) with incomplete "
                f"archives: " + "; ".join(skipped))

        need = SHORTLIST_SIZE_MIN - len(shortlist["entries"])
        take = pool[:max(0, need)]
        n = len(shortlist["entries"])
        for e in take:
            e.pop("_score", None)
            n += 1
            e["n"] = n
            shortlist["entries"].append(e)
        return len(take)
    except Exception as e:
        log(f"  NOTE: top-up skipped ({e}) — shortlist published as screened.")
        return 0


def run_screen(week):
    with pipeline_state.stage(pipeline_state.SCREENING, week=week) as st:
        return pipeline_state.finish(_run_screen(week), st)


def _run_screen(week):
    log(f"Visual screening for week {week}...")
    token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "github_token.txt")
    with open(token_file) as f:
        token = f.read().strip()

    try:
        cand = gh_fetch_json(f"candidates/candidates-{week}.json", token)
    except Exception as e:
        return False, f"could not fetch candidates-{week}.json: {e}"
    entries = cand.get("entries", [])
    if not entries:
        return False, "candidates file has no entries"
    log(f"  {len(entries)} candidate(s).")

    workdir = tempfile.mkdtemp(prefix=f"selene_screen_{week}_")
    try:
        mem = clone_memory(workdir)
        if not mem:
            return False, "memory repo clone failed (needed for brand-guide.md and push)"

        # Skip if shortlist already exists (double-fire guard)
        out_shortlist = os.path.join(mem, "shortlists", f"shortlist-{week}.json")
        if os.path.exists(out_shortlist):
            return True, f"shortlist-{week}.json already exists — nothing to do"

        img_dir = os.path.join(workdir, "candidates")
        os.makedirs(img_dir)
        cand_meta = []
        for e in entries:
            n = e.get("n")
            imgs = e.get("images") or []
            hero_path = os.path.join(img_dir, f"cand_{n}.jpg")
            ok = imgs and download_hero(imgs[0], hero_path)
            if ok:
                archive_hero(hero_path, mem, week, n)
            cand_meta.append({
                "n": n, "source": e.get("source"), "type": e.get("type"),
                "concept": e.get("concept"), "engagement": e.get("engagement"),
                "product": e.get("product"), "imageCount": len(imgs),
                "heroDownloaded": bool(ok),
            })
        cand_path = os.path.join(workdir, "candidates_meta.json")
        with open(cand_path, "w") as f:
            json.dump(cand_meta, f, indent=1)

        out_path = os.path.join(workdir, "scores.json")
        template, version = load_prompt("screening")
        try:
            import taste_brief
            taste_brief.maybe_distill()
            brief = taste_brief.brief_block("screening")
        except Exception as e:
            log(f"  taste brief unavailable ({type(e).__name__})")
            brief = "(taste brief unavailable this run)"
        try:
            import reference_drive
            reference_drive.refresh()
            reference_section = reference_drive.section(
                "style", heading="MARCUS'S OWN STYLE REFERENCES")
        except Exception as e:
            log(f"  references unavailable ({type(e).__name__}) — screening "
                f"without them")
            reference_section = ""
        prompt = template.format(
            mem=mem, img_dir=img_dir, cand_path=cand_path, out_path=out_path,
            reference_section=reference_section, taste_brief=brief,
            attribute_section=memory_digests.attribute_digest(mem),
            min_score=MIN_SCORE, smin=SHORTLIST_SIZE_MIN, smax=SHORTLIST_SIZE_MAX)
        log(f"  Invoking Claude to view and score every candidate "
            f"(prompt {version})...")
        ok, result = invoke_claude_json(
            prompt, workdir, out_path, schema=SCREEN_SCHEMA, stage="screening",
            timeout=1200)
        if not ok:
            return False, result
        by_n = {s["n"]: s for s in result.get("scores", [])}

        kept = sorted(
            [e for e in entries if by_n.get(e.get("n"), {}).get("keep")],
            key=lambda e: -by_n[e["n"]]["score"])[:SHORTLIST_SIZE_MAX]
        if not kept:
            return False, "screening kept zero candidates — check scores.json logic"

        # Renumber shortlist 1..N, carry score + rationale.
        # origN is REQUIRED (added 2026-08-17): the archived images in
        # candidate-images/<week>/ are named cand_<ORIGINAL n>.jpg, so anything
        # that later falls back to an archived copy must look it up by the
        # original candidate number, never by this display number. Without it
        # the picker silently served candidate #2's photos for shortlist #2 —
        # two different accounts showing an identical carousel.
        shortlist = {"week": week, "screened": True, "entries": []}
        for i, e in enumerate(kept, 1):
            s = by_n[e["n"]]
            ne = dict(e)
            ne["origN"] = e["n"]
            ne["n"] = i
            ne["brandScore"] = s["score"]
            ne["brandRationale"] = s.get("rationale", "")
            shortlist["entries"].append(ne)

        if len(shortlist["entries"]) < SHORTLIST_SIZE_MIN:
            added = _top_up(shortlist, mem, week)
            if added:
                log(f"  topped up with {added} carried reference(s) from "
                    f"earlier weeks (this week yielded "
                    f"{len(shortlist['entries']) - added})")
            else:
                log(f"  only {len(shortlist['entries'])} on-brand candidate(s) "
                    f"this week and nothing eligible to carry — publishing "
                    f"short rather than padding")

        os.makedirs(os.path.dirname(out_shortlist), exist_ok=True)
        with open(out_shortlist, "w") as f:
            json.dump(shortlist, f, indent=1)

        # Learning log
        vt = os.path.join(mem, "visual-taste.md")
        if not os.path.exists(vt):
            with open(vt, "w") as f:
                f.write("# Selene Visual Taste Log\n"
                        "Written by screen_runner.py after each weekly screening; "
                        "read back by the next screening so judgment improves. "
                        "Compare KEPT/cut vs what the team actually picked "
                        "(selections.md) to spot miscalibration.\n")
        with open(vt, "a") as f:
            f.write(f"\n## Screening {week} ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n")
            f.write(f"- Candidates: {len(entries)} · kept: {len(shortlist['entries'])} "
                    f"(scores {shortlist['entries'][-1]['brandScore']}-"
                    f"{shortlist['entries'][0]['brandScore']})\n")
            for s in sorted(result.get("scores", []), key=lambda x: -x.get("score", 0)):
                f.write(f"  - #{s['n']} score {s.get('score')} "
                        f"{'KEPT' if s.get('keep') else 'cut'} — {s.get('rationale','')}\n")
            if result.get("learnings"):
                f.write(f"- LEARNING: {result['learnings']}\n")
            f.write(f"- Screening prompt version: {version}\n")

        # Structured creative attributes — one row per candidate, kept or cut.
        # Cut candidates matter as much as kept ones: without them there is no
        # contrast to learn from.
        try:
            by_entry = {e.get("n"): e for e in entries}
            attr_path = os.path.join(mem, ATTR_CSV)
            new = not os.path.exists(attr_path)
            with open(attr_path, "a", newline="") as f:
                w = csv.writer(f)
                if new:
                    w.writerow(ATTR_HEADER)
                today = datetime.now().strftime("%Y-%m-%d")
                for s in result.get("scores", []):
                    a = s.get("attributes") or {}
                    e = by_entry.get(s.get("n"), {})
                    w.writerow([
                        today, week, s.get("n"), e.get("source"), e.get("type"),
                        s.get("score"), "yes" if s.get("keep") else "no",
                        e.get("postUrl", ""),
                        a.get("setting"), a.get("timeOfDay"), a.get("palette"),
                        a.get("humanPresence"), a.get("crop"),
                        a.get("textOverlay"), a.get("styling"),
                        e.get("engagement"),
                    ])
        except Exception as e:
            log(f"  NOTE: attribute CSV write failed ({e}) — scores still saved.")

        archive_gaps = []

        # Archive EVERY slide of the kept entries, not just their covers.
        # The picker renders all slides, and Instagram's CDN links die within
        # days — 2026-08-13 the shortlist showed empty boxes because slides 2
        # and 3 had never been saved anywhere. Cuts keep hero-only: the eval
        # set just needs one image per candidate for contrast.
        try:
            extra = 0
            for e in kept:
                for i, url in enumerate(e.get("images") or [], 1):
                    if i == 1:
                        continue          # hero already archived above
                    dest = os.path.join(mem, "candidate-images", week,
                                        f"cand_{e['n']}_s{i}.jpg")
                    if os.path.exists(dest):
                        continue
                    tmp = os.path.join(img_dir, f"tmp_{e['n']}_{i}.jpg")
                    if download_hero(url, tmp) and archive_slide(tmp, mem, week,
                                                                 e["n"], i):
                        extra += 1
            log(f"  archived {extra} additional slide(s) for the shortlist")

            # VERIFY, then retry the gaps once. Added 2026-08-17: on week
            # 2026-08-17 two of @coyuchi's six slides never downloaded and
            # nothing noticed — the picker showed "image expired" and the only
            # way anyone found out was Marcus looking at the page. A silent
            # gap here is unrecoverable later, because the CDN URL that would
            # have filled it is dead by the time you notice.
            missing = []
            for e in kept:
                for i, url in enumerate(e.get("images") or [], 1):
                    dest = os.path.join(
                        mem, "candidate-images", week,
                        f"cand_{e['n']}.jpg" if i == 1
                        else f"cand_{e['n']}_s{i}.jpg")
                    if not os.path.exists(dest):
                        missing.append((e, i, url, dest))

            if missing:
                log(f"  {len(missing)} slide(s) missing after the first pass — retrying")
                still = []
                for e, i, url, dest in missing:
                    tmp = os.path.join(img_dir, f"retry_{e['n']}_{i}.jpg")
                    if download_hero(url, tmp) and archive_slide(tmp, mem, week,
                                                                 e["n"], i):
                        log(f"    recovered cand_{e['n']} slide {i}")
                    else:
                        still.append(f"cand_{e['n']} slide {i}")
                if still:
                    # Loud on purpose: these images can never be recovered from
                    # the repo, so the picker will render them as expired.
                    # v1.1: ALSO carried out of this function, because until
                    # now this warning only ever reached launchd's stdout —
                    # three weeks of gaps accumulated unnoticed because the
                    # _logs/ transcript is written by claude_client at
                    # INVOCATION time and never sees anything logged after it.
                    archive_gaps.extend(still)
                    log("  WARNING: could not archive " + str(len(still)) +
                        " slide(s) — they will show as expired in the picker: " +
                        ", ".join(still))
            else:
                log("  slide archive verified complete for every kept entry")
        except Exception as e:
            log(f"  NOTE: slide archiving failed ({e}) — covers are still saved.")

        pipeline_state.mirror_to_memory(mem)

        pushed, push_msg = pipeline_state.push_with_retry(
            mem, f"Visual screening week {week}", logger=log)
        if not pushed:
            return False, f"screening done but push failed: {push_msg}"
        log(f"  Shortlist pushed: {len(shortlist['entries'])} entries. "
            f"Invite email will follow automatically.")
        msg = f"Screened {len(entries)} → kept {len(shortlist['entries'])}"
        if archive_gaps:
            msg += f" · WARNING {len(archive_gaps)} slide(s) unarchived: " + \
                   ", ".join(archive_gaps)
        return True, msg
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="Selene visual screening runner")
    parser.add_argument("--week", required=True, help="e.g. 2026-08-17")
    args = parser.parse_args()
    ok, msg = run_screen(args.week)
    print(("SUCCESS: " if ok else "FAILED: ") + msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
