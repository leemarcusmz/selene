# =============================================================================
# Selene Dreams — Screening Eval v1.0 (2026-08-12)
# eval_runner.py — Does a prompt change make the screener better, or just
#                  different?
# =============================================================================
#
# THE PROBLEM: prompts get edited, models get swapped, rubrics get reworded —
# and nobody can say whether output got better or worse. Every change is a
# guess, and guesses accumulate.
#
# THE GROUND TRUTH ALREADY EXISTS. Every week the screener produced a
# shortlist, and a human then picked from it. Those picks are labelled data:
# for each past week we know which references a person actually wanted. A good
# screener should score the picked ones above the passed ones.
#
# So the golden set builds itself from history — no manual labelling.
#
#   python3 eval_runner.py --build          # assemble the golden set
#   python3 eval_runner.py --run            # score it with the current prompt
#   python3 eval_runner.py --run --limit 20 # cheaper spot check
#
# WHAT THE NUMBERS MEAN:
#   separation  — mean score of picked minus mean score of passed. Higher is
#                 better; near zero means the screener cannot tell the
#                 difference between what a human wanted and what they didn't.
#   precision@k — of the k highest-scoring candidates, how many were actually
#                 picked (k = number picked that week). This is the metric
#                 that matches how the shortlist is really used.
#
# Run it before and after any change to prompts/screening.md, brand-guide.md
# or the model routing. A change that moves separation the wrong way is a
# regression, however good the reasoning sounded.
# =============================================================================

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime

import memory_digests
import pipeline_state
from caption_runner import clone_memory, invoke_claude_json, load_prompt, log
from screen_runner import download_hero, archive_hero, MIN_SCORE, SHORTLIST_SIZE_MIN, \
    SHORTLIST_SIZE_MAX, SCREEN_SCHEMA

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.join(BASE_DIR, "evals")
GOLDEN = os.path.join(EVAL_DIR, "golden-set.json")

WEEK_RE = re.compile(r"week\s+(\d{4}-\d{2}-\d{2})")
PICKED_RE = re.compile(r"-\s*PICKED by[^:]*:\s*(.+)")
NUM_RE = re.compile(r"#(\d+)")


# =============================================================================
# BUILD — turn history into labelled data
# =============================================================================

def parse_selections(mem_dir):
    """{week: set(picked shortlist numbers)} from selections.md."""
    path = os.path.join(mem_dir, "selections.md")
    if not os.path.exists(path):
        return {}
    picks, week = {}, None
    with open(path) as f:
        for line in f:
            m = WEEK_RE.search(line)
            if m:
                week = m.group(1)
            pm = PICKED_RE.search(line)
            if pm and week:
                nums = {int(n) for n in NUM_RE.findall(pm.group(1))}
                if nums:
                    picks.setdefault(week, set()).update(nums)
    return picks


def build_golden():
    workdir = tempfile.mkdtemp(prefix="selene_eval_build_")
    try:
        mem = clone_memory(workdir)
        if not mem:
            return False, "memory repo clone failed"
        picks = parse_selections(mem)
        if not picks:
            return False, ("selections.md has no parseable picks yet — the "
                           "golden set needs at least one week where someone "
                           "picked from a shortlist")

        entries = []
        sl_dir = os.path.join(mem, "shortlists")
        for week, picked in sorted(picks.items()):
            path = os.path.join(sl_dir, f"shortlist-{week}.json")
            if not os.path.exists(path):
                log(f"  no shortlist for week {week} — skipping")
                continue
            with open(path) as f:
                data = json.load(f)
            for e in data.get("entries", []):
                imgs = e.get("images") or []
                if not imgs:
                    continue
                entries.append({
                    "week": week, "n": e.get("n"),
                    "picked": e.get("n") in picked,
                    "source": e.get("source"), "type": e.get("type"),
                    "concept": e.get("concept"),
                    "engagement": e.get("engagement"),
                    "product": e.get("product"),
                    "heroUrl": imgs[0],
                    "archivePath": (
                        f"candidate-images/{week}/cand_{e.get('n')}.jpg"
                        if os.path.exists(os.path.join(
                            sl_dir, "..", "candidate-images", week,
                            f"cand_{e.get('n')}.jpg")) else None),
                    "originalScore": e.get("brandScore"),
                })

        if not entries:
            return False, "no shortlist entries matched the recorded picks"

        os.makedirs(EVAL_DIR, exist_ok=True)
        golden = {
            "builtAt": datetime.now().isoformat(timespec="seconds"),
            "weeks": sorted({e["week"] for e in entries}),
            "entries": entries,
        }
        with open(GOLDEN, "w") as f:
            json.dump(golden, f, indent=1)
        n_picked = sum(1 for e in entries if e["picked"])
        return True, (f"{len(entries)} labelled candidates across "
                      f"{len(golden['weeks'])} week(s) — {n_picked} picked, "
                      f"{len(entries) - n_picked} passed → {GOLDEN}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# =============================================================================
# RUN — score the golden set with the CURRENT prompt
# =============================================================================

def score_entries(entries, mem, workdir):
    img_dir = os.path.join(workdir, "candidates")
    os.makedirs(img_dir, exist_ok=True)
    meta = []
    missing = []
    for i, e in enumerate(entries, 1):
        dest = os.path.join(img_dir, f"cand_{i}.jpg")
        archived = os.path.join(mem, e["archivePath"]) if e.get("archivePath") else None
        if archived and os.path.exists(archived):
            shutil.copy(archived, dest)
            ok = True
        else:
            ok = download_hero(e["heroUrl"], dest)
            if not ok:
                missing.append(f"{e['week']}#{e['n']}")
        meta.append({"n": i, "source": e.get("source"), "type": e.get("type"),
                     "concept": e.get("concept"),
                     "engagement": e.get("engagement"),
                     "product": e.get("product"), "imageCount": 1,
                     "heroDownloaded": bool(ok)})
    cand_path = os.path.join(workdir, "candidates_meta.json")
    with open(cand_path, "w") as f:
        json.dump(meta, f, indent=1)

    got = len(entries) - len(missing)
    if got == 0:
        return None, "n/a", (
            f"none of the {len(entries)} images could be loaded — their "
            f"Instagram CDN links have expired and no archived copies exist. "
            f"Weeks screened from now on archive their images, so rebuild the "
            f"golden set once a fresh week has been screened.")
    if missing:
        log(f"  {len(missing)} image(s) unavailable (expired CDN links): "
            f"{', '.join(missing[:8])}{'...' if len(missing) > 8 else ''}")

    out_path = os.path.join(workdir, "scores.json")
    template, version = load_prompt("screening")
    prompt = template.format(
        mem=mem, img_dir=img_dir, cand_path=cand_path, out_path=out_path,
        attribute_section=memory_digests.attribute_digest(mem),
        min_score=MIN_SCORE, smin=SHORTLIST_SIZE_MIN, smax=SHORTLIST_SIZE_MAX)
    log(f"  Scoring {len(entries)} candidate(s) with prompt {version}...")
    ok, result = invoke_claude_json(prompt, workdir, out_path,
                                    schema=SCREEN_SCHEMA, stage="eval",
                                    timeout=1800)
    if not ok:
        return None, version, result
    return {s["n"]: s for s in result.get("scores", [])}, version, "ok"


def evaluate(entries, scores):
    """Separation + per-week precision@k."""
    for i, e in enumerate(entries, 1):
        s = scores.get(i) or {}
        e["newScore"] = s.get("score")
        e["newRationale"] = s.get("rationale", "")

    scored = [e for e in entries if isinstance(e.get("newScore"), (int, float))]
    picked = [e["newScore"] for e in scored if e["picked"]]
    passed = [e["newScore"] for e in scored if not e["picked"]]
    sep = ((sum(picked) / len(picked)) - (sum(passed) / len(passed))
           if picked and passed else None)

    per_week = []
    for week in sorted({e["week"] for e in scored}):
        wk = [e for e in scored if e["week"] == week]
        k = sum(1 for e in wk if e["picked"])
        if not k:
            continue
        top = sorted(wk, key=lambda e: -e["newScore"])[:k]
        hits = sum(1 for e in top if e["picked"])
        per_week.append({"week": week, "k": k, "hits": hits,
                         "precision": hits / k, "n": len(wk)})

    return {
        "scored": len(scored),
        "meanPicked": sum(picked) / len(picked) if picked else None,
        "meanPassed": sum(passed) / len(passed) if passed else None,
        "separation": sep,
        "perWeek": per_week,
        "meanPrecision": (sum(w["precision"] for w in per_week) / len(per_week)
                          if per_week else None),
    }


def write_report(entries, stats, version):
    os.makedirs(EVAL_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    path = os.path.join(EVAL_DIR, f"eval-{stamp}.md")
    with open(path, "w") as f:
        f.write(f"# Screening eval — {stamp}\n\n")
        f.write(f"- Screening prompt version: `{version}`\n")
        f.write(f"- Candidates scored: {stats['scored']}\n")
        if stats["separation"] is not None:
            f.write(f"- Mean score PICKED: {stats['meanPicked']:.2f}\n")
            f.write(f"- Mean score PASSED: {stats['meanPassed']:.2f}\n")
            f.write(f"- **Separation: {stats['separation']:+.2f}** "
                    f"(higher is better; near zero means the screener cannot "
                    f"tell picked from passed)\n")
        if stats["meanPrecision"] is not None:
            f.write(f"- **Mean precision@k: {stats['meanPrecision']:.0%}**\n")
        f.write("\n## Per week\n\n| Week | Candidates | Picked (k) | Hits in top-k | Precision |\n")
        f.write("|---|---|---|---|---|\n")
        for w in stats["perWeek"]:
            f.write(f"| {w['week']} | {w['n']} | {w['k']} | {w['hits']} | "
                    f"{w['precision']:.0%} |\n")

        f.write("\n## Disagreements worth reading\n\n")
        scored = [e for e in entries
                  if isinstance(e.get("newScore"), (int, float))]
        misses = sorted([e for e in scored if e["picked"]],
                        key=lambda e: e["newScore"])[:5]
        false_hi = sorted([e for e in scored if not e["picked"]],
                          key=lambda e: -e["newScore"])[:5]
        f.write("**Picked by a human, scored low here** — the screener would "
                "have cut these:\n\n")
        for e in misses:
            f.write(f"- {e['week']} #{e['n']} · {e['newScore']}/12 · "
                    f"{e.get('source')} — {e.get('concept','')} "
                    f"({e['newRationale']})\n")
        f.write("\n**Scored high here, not picked** — plausible but not what "
                "the team wanted:\n\n")
        for e in false_hi:
            f.write(f"- {e['week']} #{e['n']} · {e['newScore']}/12 · "
                    f"{e.get('source')} — {e.get('concept','')} "
                    f"({e['newRationale']})\n")
    return path


def run_eval(limit=None):
    if not os.path.exists(GOLDEN):
        return False, f"no golden set yet — run: python3 eval_runner.py --build"
    with open(GOLDEN) as f:
        golden = json.load(f)
    entries = golden.get("entries", [])
    if limit:
        entries = entries[:limit]
    if not entries:
        return False, "golden set is empty"

    workdir = tempfile.mkdtemp(prefix="selene_eval_run_")
    try:
        mem = clone_memory(workdir)
        if not mem:
            return False, "memory repo clone failed (brand-guide.md required)"
        scores, version, msg = score_entries(entries, mem, workdir)
        if scores is None:
            return False, msg
        stats = evaluate(entries, scores)
        path = write_report(entries, stats, version)

        sep = stats["separation"]
        prec = stats["meanPrecision"]
        summary = (
            f"separation {sep:+.2f}" if sep is not None else "separation n/a")
        if prec is not None:
            summary += f" · precision@k {prec:.0%}"
        summary += f" · prompt {version} · report {path}"
        log(f"  {summary}")
        return True, summary
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="Selene screening eval")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--build", action="store_true",
                   help="Build the golden set from past shortlists + picks")
    g.add_argument("--run", action="store_true",
                   help="Score the golden set with the current prompt")
    ap.add_argument("--limit", type=int,
                    help="Only score the first N candidates (cheaper)")
    args = ap.parse_args()

    ok, msg = (build_golden() if args.build else run_eval(args.limit))
    print(("SUCCESS: " if ok else "FAILED: ") + msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
