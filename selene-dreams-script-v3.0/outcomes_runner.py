# =============================================================================
# Selene Dreams — Outcome Join v1.0 (2026-08-12)
# outcomes_runner.py — Connect published posts back to what produced them
# =============================================================================
#
# THE GAP THIS CLOSES: the pipeline learned what looks on-brand (the screener),
# what humans pick (selections.md), and what it generated (prompt-playbook +
# QA). It never learned what actually WORKED, because nothing connected a live
# Instagram post to the queue row, prompt, QA score and caption behind it.
#
# The data was already there. The Sunday scrape collects Selene's own posts
# along with the competitors'. The only missing link was identity — which
# scraped post is row #14? That link is now one paste: the live post URL into
# Generation Status column O when you publish.
#
# This runner then:
#   1. Reads every row that has a post URL in column O.
#   2. Pulls the latest own-brand metrics from the Apify posts dataset.
#   3. Matches them by Instagram shortcode (robust to /p/ vs /reel/, query
#      strings and trailing slashes).
#   4. Joins in the QA score for that row from generation-scores.csv.
#   5. Writes post-outcomes.csv to the memory repo and pushes.
#
# Every downstream reader — prompt playbook, copy playbook, visual taste, the
# monthly deep-dive — can then reason about outcomes instead of intentions.
#
# Deliberately re-writes the whole CSV each run rather than appending: metrics
# keep moving after publication, so the newest read of a post supersedes the
# older one.
#
# CLI usage:
#   python3 outcomes_runner.py
# =============================================================================

import csv
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime

import config
import pipeline_state
from google_services import get_google_services, get_gs_sheet
from caption_runner import clone_memory, log

OUTCOMES_CSV = "post-outcomes.csv"
SCORES_CSV = "generation-scores.csv"
OUTCOMES_HEADER = [
    "readAt", "row", "postUrl", "shortcode", "postDate", "type",
    "likes", "comments", "views", "qaAvgScore", "qaImages",
    "fabric", "productType", "variant",
]

SHORTCODE_RE = re.compile(r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)")


def shortcode(url):
    """Instagram post identity, normalised. Returns None if not a post URL."""
    m = SHORTCODE_RE.search(str(url or ""))
    return m.group(1) if m else None


# =============================================================================
# SOURCES
# =============================================================================

def read_published_rows(queue):
    """Rows carrying a post URL in Generation Status col O."""
    gs = get_gs_sheet(queue)
    if gs is None:
        return []
    values = gs.get_all_values()
    out = []
    for i, r in enumerate(values, start=1):
        if i < config.GS_FIRST_DATA_ROW:
            continue

        def cell(col):
            return str(r[col - 1]).strip() if len(r) >= col else ""

        num, url = cell(config.GS_COL_NUMBER), cell(config.GS_COL_POST_URL)
        sc = shortcode(url)
        if not (num.isdigit() and sc):
            continue
        out.append({"row": int(num), "postUrl": url, "shortcode": sc,
                    "postDate": cell(config.GS_COL_POST_DATE)})
    return out


def read_queue_products(queue, rows):
    """Fabric / type / variant per row, so outcomes are readable without a
    second lookup."""
    products = {}
    for r in rows:
        try:
            vals = queue.row_values(r["row"] + 1)
            while len(vals) < config.TOTAL_COLS:
                vals.append("")
            products[r["row"]] = {
                "fabric": vals[config.COL_FABRIC].strip(),
                "productType": vals[config.COL_PRODUCT_TYPE].strip(),
                "variant": vals[config.COL_VARIANT].strip(),
            }
        except Exception as e:
            log(f"  NOTE: could not read queue row {r['row']}: {e}")
            products[r["row"]] = {}
    return products


def fetch_own_posts():
    """Latest scraped metrics for Selene's own account.

    cb= cache-buster is mandatory: Apify/CDN serves stale week-old responses
    for previously-used URLs (root-caused 2026-07-27), which would silently
    record last week's numbers as this week's outcome.
    """
    url = (f"https://api.apify.com/v2/actor-tasks/{config.APIFY_POSTS_TASK}"
           f"/runs/last/dataset/items?token={config.APIFY_TOKEN}"
           f"&status=SUCCEEDED&format=json&clean=true"
           f"&fields=ownerUsername,type,url,likesCount,commentsCount,"
           f"videoViewCount,timestamp&cb={random.randint(10**6, 10**9)}")

    def _get():
        with urllib.request.urlopen(url, timeout=120) as r:
            return json.loads(r.read().decode())

    items = pipeline_state.retry(_get, label="apify posts", logger=log)
    own = {}
    for it in items:
        if str(it.get("ownerUsername", "")).lower() != config.OWN_IG_USERNAME:
            continue
        sc = shortcode(it.get("url"))
        if sc:
            own[sc] = it
    return own


def read_qa_scores(mem_dir):
    """Average generation QA score per row, from qa_runner's CSV."""
    path = os.path.join(mem_dir, SCORES_CSV)
    if not os.path.exists(path):
        return {}
    agg = {}
    try:
        with open(path) as f:
            for rec in csv.DictReader(f):
                try:
                    row, score = int(rec["row"]), float(rec["score"])
                except (KeyError, ValueError, TypeError):
                    continue
                agg.setdefault(row, []).append(score)
    except Exception as e:
        log(f"  NOTE: could not read {SCORES_CSV}: {e}")
    return {r: (sum(v) / len(v), len(v)) for r, v in agg.items()}


# =============================================================================
# CORE
# =============================================================================

def run_outcomes():
    with pipeline_state.stage(pipeline_state.OUTCOMES) as st:
        return pipeline_state.finish(_run_outcomes(), st)


def _run_outcomes():
    log("Outcome join — matching published posts to what produced them...")
    sheets_client, _drive = get_google_services()
    queue = sheets_client.open_by_key(config.GOOGLE_SHEET_ID) \
        .worksheet(config.GOOGLE_SHEET_NAME)

    rows = read_published_rows(queue)
    if not rows:
        return True, ("no rows carry a post URL in Generation Status col O yet "
                      "— paste live post URLs there and this fills itself in")
    log(f"  {len(rows)} published row(s) with a post URL.")

    try:
        own = fetch_own_posts()
    except Exception as e:
        return False, f"Apify read failed: {e}"
    log(f"  {len(own)} own-brand post(s) in the latest scrape.")

    workdir = tempfile.mkdtemp(prefix="selene_outcomes_")
    try:
        mem = clone_memory(workdir)
        if not mem:
            return False, "memory repo clone failed — nowhere to write outcomes"

        products = read_queue_products(queue, rows)
        qa = read_qa_scores(mem)

        matched, unmatched = 0, []
        read_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        records = []
        for r in rows:
            post = own.get(r["shortcode"])
            if not post:
                unmatched.append(r["row"])
            p = products.get(r["row"], {})
            qa_avg, qa_n = qa.get(r["row"], ("", ""))
            records.append([
                read_at, r["row"], r["postUrl"], r["shortcode"], r["postDate"],
                (post or {}).get("type", ""),
                (post or {}).get("likesCount", ""),
                (post or {}).get("commentsCount", ""),
                (post or {}).get("videoViewCount", ""),
                f"{qa_avg:.1f}" if isinstance(qa_avg, float) else "",
                qa_n, p.get("fabric", ""), p.get("productType", ""),
                p.get("variant", ""),
            ])
            matched += bool(post)

        out_path = os.path.join(mem, OUTCOMES_CSV)
        with open(out_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(OUTCOMES_HEADER)
            w.writerows(sorted(records, key=lambda x: x[1]))

        pipeline_state.mirror_to_memory(mem)
        pushed, push_msg = pipeline_state.push_with_retry(
            mem, f"Post outcomes {datetime.now():%Y-%m-%d}", logger=log)
        if not pushed:
            return False, f"outcomes written but push failed: {push_msg}"

        msg = f"{matched}/{len(rows)} published rows matched to scraped metrics"
        if unmatched:
            # Normal for posts published after the last Sunday scrape.
            msg += (f" · not yet in a scrape: rows "
                    f"{', '.join(map(str, unmatched))}")
        log(f"  {msg}")
        return True, msg
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main():
    ok, msg = run_outcomes()
    print(("SUCCESS: " if ok else "FAILED: ") + msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
