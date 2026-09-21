#!/usr/bin/env python3
"""Repair missing archived slides for a published week.

WHY: candidate-images/<week>/ should hold one file per slide of every kept
entry. When a download failed at screening time the file is simply absent, and
the picker shows "image expired" — the original CDN URL is dead by then, so
there is nothing to retry against.

This re-scrapes the affected POSTS through Apify to obtain fresh CDN URLs,
downloads only the missing slides, archives them and pushes.

Usage:  python3 repair_slides.py 2026-08-17
        python3 repair_slides.py 2026-08-17 --dry-run

Cost: one Apify actor run per affected post (cents). Requires network, so it
runs on the Mac, not in a cloud session.
"""
import json, os, subprocess, sys, tempfile, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from screen_runner import download_hero, archive_slide   # reuse, don't reimplement

import config
# Actor runs need the RUN-scoped token, not the read-only one — see config.py.
APIFY_TOKEN = config.APIFY_RUN_TOKEN
ACTOR = "apify~instagram-scraper"

week = None
dry = "--dry-run" in sys.argv
for a in sys.argv[1:]:
    if not a.startswith("--"):
        week = a
if not week:
    sys.exit("usage: python3 repair_slides.py YYYY-MM-DD [--dry-run]")

with open(os.path.join(HERE, "github_token.txt")) as f:
    TOKEN = f.read().strip()
REPO = f"https://x-access-token:{TOKEN}@github.com/leemarcusmz/selene-ig-memory.git"

tmp = tempfile.mkdtemp(prefix="selene-repair-")
mem = os.path.join(tmp, "mem")
print("cloning...")
subprocess.run(["git", "clone", "--quiet", "--depth", "1", REPO, mem], check=True)

sl_path = os.path.join(mem, "shortlists", f"shortlist-{week}.json")
if not os.path.exists(sl_path):
    sys.exit(f"no shortlist for {week}")
entries = json.load(open(sl_path))["entries"]

# What is missing?
gaps = {}          # postUrl -> {"n": origN, "slides": [i, ...]}
for e in entries:
    n = e.get("origN", e.get("n"))
    for i in range(1, len(e.get("images") or []) + 1):
        name = f"cand_{n}.jpg" if i == 1 else f"cand_{n}_s{i}.jpg"
        if not os.path.exists(os.path.join(mem, "candidate-images", week, name)):
            gaps.setdefault(e["postUrl"], {"n": n, "slides": []})["slides"].append(i)

if not gaps:
    print(f"{week}: nothing missing — every slide is archived.")
    sys.exit(0)

for url, g in gaps.items():
    print(f"  missing: cand_{g['n']} slides {g['slides']}  ({url})")
if dry:
    print("\n--dry-run, stopping before the Apify call.")
    sys.exit(0)

# Re-scrape those posts for fresh image URLs
api = (f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items"
       f"?token={APIFY_TOKEN}&format=json&clean=true&cb={int(time.time())}")
body = json.dumps({"directUrls": list(gaps.keys()),
                   "resultsType": "posts", "resultsLimit": 1}).encode()
print(f"\nre-scraping {len(gaps)} post(s) via Apify...")
req = urllib.request.Request(api, data=body,
                             headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=300) as r:
        items = json.load(r)
except Exception as ex:
    sys.exit(f"Apify call failed: {ex}")

by_url = {it.get("url"): it for it in items if it.get("url")}
fixed = failed = 0
for url, g in gaps.items():
    item = by_url.get(url)
    if not item:
        print(f"  ! no fresh data returned for {url}")
        failed += len(g["slides"]); continue
    fresh = item.get("images") or ([item["displayUrl"]] if item.get("displayUrl") else [])
    for i in g["slides"]:
        if i > len(fresh):
            print(f"  ! cand_{g['n']} slide {i}: post only has {len(fresh)} images now")
            failed += 1; continue
        dest_tmp = os.path.join(tmp, f"r_{g['n']}_{i}.jpg")
        if download_hero(fresh[i - 1], dest_tmp) and \
           archive_slide(dest_tmp, mem, week, g["n"], i):
            print(f"  recovered cand_{g['n']} slide {i}")
            fixed += 1
        else:
            print(f"  ! cand_{g['n']} slide {i}: download/archive failed")
            failed += 1

if not fixed:
    sys.exit(f"\nnothing recovered ({failed} still missing).")

subprocess.run(["git", "-C", mem, "add", "-A"], check=True)
subprocess.run(["git", "-C", mem, "commit", "-q", "-m",
                f"Repair {fixed} missing archived slide(s) for {week}"], check=True)
subprocess.run(["git", "-C", mem, "push", "-q"], check=True)
print(f"\npushed: {fixed} recovered, {failed} still missing. Reload the picker.")
