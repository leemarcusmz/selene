"""
post_metrics.py — read Instagram results back for published CAROUSELS
=============================================================================
VERSION 1.1 — 2026-09-16

WHY
    The reel lane reads its results back (reel_metrics, 72h and 7d). The
    carousel lane only had outcomes_runner, which depends on the weekly Apify
    scrape: likes, comments and views, a week late, and only when the scrape
    ran. The taste layer ([[taste_store]]) needs the same shape of number for
    every lane, read the same way, at the same ages — otherwise "what worked"
    is not comparable across lanes and cannot be learned from.

WHAT
    Every Generation Status row with a live URL in column O (image lane) and
    every educational queue row with a permalink (edu lane) is read at the
    same two windows reel_metrics uses (reel_config.METRIC_WINDOWS: 72h, 7d),
    once per window, into _state/post-metrics.json keyed by shortcode.
    Same rules as reel_metrics: a window is read ONCE; an unreadable window
    is retried a bounded number of times and never recorded as zeros; the
    metric set is negotiated once per media type and cached; nothing here
    raises into a caller.

MEDIA ID
    Insights need the media id, and the sheets hold only the permalink. The
    id is resolved ONCE per post by walking /{ig-user}/media (permalink,id)
    and cached; publish_runner also writes "media <id>" into the system
    remark, which is tried first because it is free.

CHANGELOG
    1.1  2026-09-16  Hand-posted items found by posted_sheet's account walk
                     (state["manual"]) get windows read too, lane "manual",
                     so the Posted Content sheet shows numbers for the whole
                     grid. Media ids come from the walk, no extra lookups.
    1.0  2026-09-16  First build, for the taste layer.
=============================================================================
"""

import json
import os
import re
from datetime import datetime, timedelta

import config
import reel_config

VERSION = "1.0"

STATE_PATH = os.path.join(reel_config.BASE_DIR, "_state", "post-metrics.json")

# Metrics Instagram answers for feed/carousel media in Graph v21/v22.
WANTED = ["views", "reach", "likes", "comments", "shares", "saved",
          "total_interactions"]

SHORTCODE_RE = re.compile(r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)")
MEDIA_RE = re.compile(r"media\s+(\d{6,})")
MAX_PER_PASS = 6


def log(msg):
    print(f"[post_metrics] {msg}", flush=True)


def shortcode(url):
    m = SHORTCODE_RE.search(str(url or ""))
    return m.group(1) if m else None


def load_state():
    try:
        with open(STATE_PATH) as f:
            s = json.load(f)
        s.setdefault("posts", {})
        return s
    except Exception:
        return {"version": VERSION, "posts": {}, "media_index": {},
                "fields": None}


def save_state(s):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f, indent=2)
    os.replace(tmp, STATE_PATH)


# ── sources: which posts exist ──────────────────────────────────────────────

def _image_lane_rows():
    """[{key, lane, url, posted, ref, remark}] from Generation Status col O."""
    out = []
    try:
        from google_services import get_sheets_client
        gc = get_sheets_client()
        ss = gc.open_by_key(config.GOOGLE_SHEET_ID)
        gs = ss.worksheet(config.GS_SHEET_NAME)
        vals = gs.get_all_values()
    except Exception as e:
        log(f"image-lane sheet unreadable ({type(e).__name__}) — skipping")
        return out
    for i, r in enumerate(vals, start=1):
        if i < config.GS_FIRST_DATA_ROW:
            continue
        cell = lambda c: str(r[c - 1]).strip() if len(r) >= c else ""
        url = cell(config.GS_COL_POST_URL)
        sc = shortcode(url)
        num = cell(config.GS_COL_NUMBER)
        if not sc or not num.isdigit():
            continue
        out.append({"key": sc, "lane": "images", "url": url,
                    "posted": cell(config.GS_COL_POST_DATE),
                    "ref": f"row #{num}",
                    "remark": cell(config.GS_COL_SYS_REMARK)})
    return out


def _edu_rows():
    """Educational queue rows with a permalink in column R."""
    out = []
    try:
        import sys
        edu_dir = os.path.normpath(os.path.join(
            reel_config.BASE_DIR, "..", "selene-dreams-educational-v1.0"))
        if edu_dir not in sys.path:
            sys.path.insert(0, edu_dir)
        import config_edu as C
        from google_services import get_sheets_client
        gc = get_sheets_client()
        ss = gc.open_by_key(C.EDU_QUEUE_SHEET_ID)
        q = ss.worksheet("Generation Queue").get_all_values()
    except Exception as e:
        log(f"edu sheet unreadable ({type(e).__name__}) — skipping")
        return out
    for r in q[1:]:
        r = (r + [""] * 19)[:19]
        sc = shortcode(r[17])                       # R permalink
        if not sc:
            continue
        out.append({"key": sc, "lane": "educational", "url": r[17].strip(),
                    "posted": "", "ref": f"topic #{r[3].strip()} row #{r[0].strip()}",
                    "remark": r[18]})
    return out


def _manual_rows(state):
    out = []
    for sc, rec in (state.get("manual") or {}).items():
        if sc.startswith("_") or not rec.get("media_id"):
            continue
        first = (rec.get("caption", "") or "").split("\n")[0][:70]
        out.append({"key": sc, "lane": "manual", "url": rec.get("url", ""),
                    "posted": rec.get("timestamp", ""), "ref": first or rec.get("media_type", "") or sc,
                    "remark": f"media {rec['media_id']}"})
    return out


def known_posts(state=None):
    """Never raises. Either sheet being down just means fewer posts."""
    try:
        return _image_lane_rows() + _edu_rows() + _manual_rows(state or {})
    except Exception as e:
        log(f"could not list posts ({type(e).__name__})")
        return []


# ── Graph ───────────────────────────────────────────────────────────────────

def _get(path, params):
    import reel_metrics
    return reel_metrics._get(path, params)


def _media_id_for(sc, remark, state):
    idx = state.setdefault("media_index", {})
    if sc in idx:
        return idx[sc]
    m = MEDIA_RE.search(remark or "")
    if m:
        idx[sc] = m.group(1)
        return idx[sc]
    # Walk the account's media once; cache every permalink we see.
    import reel_runner
    try:
        after = None
        for _ in range(10):
            params = {"fields": "id,permalink", "limit": 100}
            if after:
                params["after"] = after
            r = _get(f"{reel_runner.IG_USER_ID}/media", params)
            for it in r.get("data", []):
                s = shortcode(it.get("permalink"))
                if s:
                    idx[s] = it["id"]
            after = (r.get("paging") or {}).get("cursors", {}).get("after")
            if sc in idx or not r.get("paging", {}).get("next"):
                break
    except Exception as e:
        log(f"media walk failed ({str(e)[:100]})")
    return idx.get(sc)


def _probe(media_id):
    try:
        r = _get(f"{media_id}/insights", {"metric": ",".join(WANTED)})
        names = [i.get("name") for i in r.get("data", []) if i.get("name")]
        if names:
            return names
    except Exception as e:
        log(f"full metric set rejected ({str(e)[:80]}) — testing one at a time")
    ok = []
    for m in WANTED:
        try:
            if _get(f"{media_id}/insights", {"metric": m}).get("data"):
                ok.append(m)
        except Exception:
            pass
    return ok


def fetch(media_id, state):
    """{metric: value}. Empty when nothing readable. Never raises."""
    out = {}
    node_ok = False
    try:
        node = _get(media_id, {"fields": "like_count,comments_count,timestamp,"
                                         "media_type,media_product_type"})
        node_ok = True
        if node.get("like_count") is not None:
            out["likes"] = node["like_count"]
        if node.get("comments_count") is not None:
            out["comments"] = node["comments_count"]
        if node.get("timestamp"):
            out["_timestamp"] = node["timestamp"]
        if node.get("media_type"):
            out["_media_type"] = node["media_type"]
    except Exception as e:
        log(f"media node unreadable for {media_id} ({str(e)[:100]})")
        return out
    fields = state.get("fields")
    if fields is None:
        fields = _probe(media_id)
        state["fields"] = fields
        log(f"carousel insight metrics supported: {', '.join(fields) or 'none'}")
    if fields:
        try:
            r = _get(f"{media_id}/insights", {"metric": ",".join(fields)})
            for it in r.get("data", []):
                v = (it.get("values") or [{}])[0].get("value")
                if v is not None:
                    out[it["name"]] = v
        except Exception as e:
            log(f"insights unreadable ({str(e)[:100]})")
    return out


# ── windows ─────────────────────────────────────────────────────────────────

def _posted_at(rec):
    ts = rec.get("timestamp") or ""
    try:
        return datetime.fromisoformat(ts.replace("+0000", "+00:00")).astimezone().replace(tzinfo=None)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(rec.get("posted", "")[:16], fmt)
        except Exception:
            continue
    return None


def due_windows(rec, now):
    at = _posted_at(rec)
    if at is None:
        return []
    have = rec.setdefault("metrics", {})
    tries = rec.setdefault("unreadable", {})
    due = []
    for label, hours in reel_config.METRIC_WINDOWS:
        if label in have:
            continue
        if tries.get(label, 0) >= reel_config.METRICS_UNREADABLE_RETRIES:
            continue
        if now >= at + timedelta(hours=hours):
            due.append(label)
    return due


def pass_over(state=None, limit=None):
    """Read every due window, bounded. Returns readings taken. Never raises."""
    own = state is None
    state = state or load_state()
    limit = MAX_PER_PASS if limit is None else limit
    taken = 0
    try:
        for p in known_posts(state):
            existing = state["posts"].get(p["key"])
            if p["lane"] == "manual" and existing and existing.get("lane") != "manual":
                continue                          # the system knows it; the walk adds nothing
            rec = state["posts"].setdefault(p["key"], {
                "lane": p["lane"], "url": p["url"], "ref": p["ref"],
                "posted": p["posted"]})
            rec["ref"] = p["ref"] or rec.get("ref", "")
            if p["lane"] != "manual" and rec.get("lane") == "manual":
                rec["lane"] = p["lane"]          # a system post found by the walk first
                rec["ref"] = p["ref"] or rec.get("ref", "")
            if p.get("remark"):
                rec["remark"] = p["remark"]
            if not rec.get("timestamp") and not rec.get("posted"):
                rec["posted"] = p["posted"]
        now = datetime.now()
        for sc, rec in state["posts"].items():
            if taken >= limit:
                break
            if not rec.get("media_id"):
                rec["media_id"] = _media_id_for(
                    sc, rec.get("remark", ""), state)
                if not rec["media_id"]:
                    continue
            if not rec.get("timestamp"):
                # One node read to learn the real publish time.
                r = fetch(rec["media_id"], state)
                if r.get("_timestamp"):
                    rec["timestamp"] = r["_timestamp"]
                    rec["media_type"] = r.get("_media_type", "")
                else:
                    continue
            for label in due_windows(rec, now):
                r = fetch(rec["media_id"], state)
                reading = {k: v for k, v in r.items() if not k.startswith("_")}
                if reading:
                    reading["read_at"] = now.isoformat(timespec="minutes")
                    rec["metrics"][label] = reading
                    log(f"{rec.get('ref')} ({rec['lane']}): {label} read")
                else:
                    rec["unreadable"][label] = rec["unreadable"].get(label, 0) + 1
                taken += 1
                if taken >= limit:
                    break
    except Exception as e:
        log(f"WARNING: pass failed ({type(e).__name__}: {str(e)[:100]})")
    if own and taken:
        save_state(state)
    return taken


def latest(rec):
    have = rec.get("metrics") or {}
    for label, _ in reversed(reel_config.METRIC_WINDOWS):
        if label in have:
            return label, have[label]
    return None, {}


def report(state=None):
    state = state or load_state()
    print(f"\nCAROUSEL METRICS — {len(state['posts'])} post(s) known\n")
    for sc, rec in sorted(state["posts"].items(),
                          key=lambda kv: kv[1].get("timestamp", ""), reverse=True):
        label, m = latest(rec)
        line = (f"{label}: reach {m.get('reach', '-')} · saves {m.get('saved', '-')} "
                f"· shares {m.get('shares', '-')} · likes {m.get('likes', '-')}"
                if label else "no window read yet")
        print(f"  {rec.get('lane'):<12} {rec.get('ref', ''):<22} {line}")
    print()


if __name__ == "__main__":
    import sys
    if "--run" in sys.argv:
        s = load_state()
        n = pass_over(s)
        save_state(s)
        print(f"{n} reading(s) taken")
    report()
