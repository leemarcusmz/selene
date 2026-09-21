#!/usr/bin/env python3
"""Backfill origN into existing shortlists (one-off, 2026-08-17).

WHY: candidate-images/<week>/cand_<n>.jpg is named by the ORIGINAL candidate
number, but the shortlist renumbers survivors 1..N and never recorded the
original. When an Instagram CDN URL expired, the picker recovered the archived
image by DISPLAY number and served a different post's photos — on 2026-08-17
two entries from different accounts showed an identical carousel.

screen_runner.py now writes origN for every future week. This repairs the
weeks already published, by matching each shortlist entry's postUrl back to
the candidates file for the same week.

Run:  python3 backfill_orign.py
"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "github_token.txt")) as f:
    TOKEN = f.read().strip()
REPO = f"https://x-access-token:{TOKEN}@github.com/leemarcusmz/selene-ig-memory.git"

tmp = tempfile.mkdtemp(prefix="selene-origN-")
mem = os.path.join(tmp, "mem")
print("cloning…")
subprocess.run(["git", "clone", "--quiet", "--depth", "1", REPO, mem], check=True)

changed = []
sl_dir, cd_dir = os.path.join(mem, "shortlists"), os.path.join(mem, "candidates")
for fn in sorted(os.listdir(sl_dir)):
    if not fn.startswith("shortlist-") or not fn.endswith(".json"):
        continue
    week = fn[len("shortlist-"):-len(".json")]
    cand_path = os.path.join(cd_dir, f"candidates-{week}.json")
    if not os.path.exists(cand_path):
        print(f"  {week}: no candidates file — skipped (pre-dates the candidates flow)")
        continue

    sl_path = os.path.join(sl_dir, fn)
    sl = json.load(open(sl_path))
    cd = json.load(open(cand_path))
    by_url = {c.get("postUrl"): c.get("n") for c in cd.get("entries", []) if c.get("postUrl")}

    hits = misses = already = 0
    for e in sl.get("entries", []):
        if e.get("origN") is not None:
            already += 1
            continue
        o = by_url.get(e.get("postUrl"))
        if o is None:
            misses += 1
            print(f"     ! {week} entry n={e.get('n')} {e.get('source')} — postUrl not in candidates; left alone")
            continue
        e["origN"] = o
        hits += 1

    if hits:
        json.dump(sl, open(sl_path, "w"), indent=1)
        changed.append(week)
    print(f"  {week}: {hits} fixed, {misses} unmatched, {already} already had origN")

if not changed:
    print("\nNothing to change.")
    sys.exit(0)

print(f"\ncommitting weeks: {', '.join(changed)}")
subprocess.run(["git", "-C", mem, "add", "-A"], check=True)
subprocess.run(["git", "-C", mem, "commit", "-q", "-m",
                "Backfill origN into shortlists (archived-image recovery fix)"], check=True)
subprocess.run(["git", "-C", mem, "push", "-q"], check=True)
print("pushed. Reload the picker — expired images now recover the correct post.")
