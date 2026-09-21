"""
posted_sheet.py — ONE sheet for every published post, every lane, with room
                  for Marcus to rate and comment on each
=============================================================================
VERSION 1.0 — 2026-09-16

WHY
    Marcus: "create a new sheet just for all posted contents so I can give
    comments for each one instead of just in the trial reels sheet". Until
    now feedback lived in three places (Trial Reel Q/W, image-lane Generation
    Status col N, edu Generation Status col O). This is the one place.

THE SHEET: "Selene Dreams - Posted Content"
    Drive: Selene Bedding / 10. AI Generation (config.DRIVE_PARENT_FOLDER_ID)
    Created 2026-09-16 in MARCUS'S OWN Drive by CSV import, then shared to the
    service account as writer (the order that keeps it in his Drive).

    Tab "Posts" — one row per published post, ANY lane, keyed by permalink:
      A #  B Lane  C Posted  D What  E Choices  F Permalink
      G Views  H Reach  I Likes  J Comments  K Shares  L Saves  M Metrics window
      N Rating (1-5)  O Notes                      <- HIS, never written
    Lanes: reels · images · educational · manual (published by hand — found by
    walking the Instagram account, so the whole grid is commentable).

    Tab "Taste Notes" — general directions, moved here from the Trial Reel
    sheet: A Date · B Note · C Applies to · D Seen (the lane stamps D).

ONE-WAY + READ-BACK, FAIL-OPEN
    Like the Trial Reel mirror: state files stay the truth for what has
    posted; this sheet is a VIEW plus an INPUT (N/O and Taste Notes). Every
    function swallows its own errors; a dead sheet never stops a publish, and
    a rebuild never loses his cells because rows are matched by permalink,
    not position.

CHANGELOG
    1.0  2026-09-16  First build.
=============================================================================
"""

import re
from datetime import datetime

import config
import reel_config

VERSION = "1.0"

SHEET_ID = getattr(config, "POSTED_SHEET_ID", "19evO6rmh-O9jMmQVUqu0ctV8Z9RRXArFt2xyP6i0bfE")
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"
POSTS_TAB = "Posts"
TASTE_TAB = "Taste Notes"

HEADERS = ["#", "Lane", "Posted", "What", "Choices", "Permalink",
           "Views", "Reach", "Likes", "Comments", "Shares", "Saves",
           "Metrics window", "Rating", "Notes"]
TASTE_HEADERS = ["Date", "Note", "Applies to", "Seen"]
WRITTEN_COLS = 13                 # A-M
PERMALINK_COL = 5                 # zero-based F
RATING_COL, NOTES_COL = 13, 14    # N, O
MANUAL_WALK_LIMIT = getattr(config, "POSTED_MANUAL_WALK", 50)

SHORTCODE_RE = re.compile(r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)")


def log(msg):
    print(f"[posted_sheet] {msg}", flush=True)


def shortcode(url):
    m = SHORTCODE_RE.search(str(url or ""))
    return m.group(1) if m else ""


def _open(tab=POSTS_TAB):
    from google_services import get_sheets_client
    ss = get_sheets_client().open_by_key(SHEET_ID)
    headers = TASTE_HEADERS if tab == TASTE_TAB else HEADERS
    try:
        ws = ss.worksheet(tab)
    except Exception:
        # The CSV import leaves one tab named after the file; adopt it for
        # Posts rather than orphaning the imported header row.
        tabs = ss.worksheets()
        if tab == POSTS_TAB and len(tabs) == 1:
            ws = tabs[0]
            ws.update_title(tab)
        else:
            ws = ss.add_worksheet(title=tab, rows=500, cols=len(headers))
            ws.update(values=[headers], range_name="A1",
                      value_input_option="RAW")
    return ws


# ── what should be in the sheet ─────────────────────────────────────────────

def _reel_posts():
    out = []
    try:
        import reel_runner, reel_metrics
        state = reel_runner.load_state()
        for rec in (state.get("videos") or {}).values():
            for run in rec.get("runs", []):
                link = run.get("permalink") or ""
                if not link:
                    continue
                m = {}
                try:
                    m = reel_metrics.latest(run) or {}
                except Exception:
                    pass
                label = next((lab for lab, _ in reversed(reel_config.METRIC_WINDOWS)
                              if (run.get("metrics") or {}).get(lab) is m), "")
                out.append({
                    "lane": "reels", "posted": run.get("at", "")[:16].replace("T", " "),
                    "what": f'{rec.get("filename", "")} · "{run.get("hook", "")}"',
                    "choices": ", ".join(x for x in (
                        run.get("hook_pattern_id"), run.get("style"),
                        run.get("hook_mode")) if x),
                    "permalink": link, "metrics": m, "window": label,
                    "watch": m.get("ig_reels_avg_watch_time"),
                })
    except Exception as e:
        log(f"reel posts unavailable ({type(e).__name__})")
    return out


def _carousel_posts():
    out = []
    try:
        import post_metrics
        ps = post_metrics.load_state()
        for sc, rec in ps.get("posts", {}).items():
            label, m = post_metrics.latest(rec)
            out.append({
                "lane": rec.get("lane", "images"),
                "posted": (rec.get("timestamp") or rec.get("posted") or "")[:16].replace("T", " "),
                "what": rec.get("ref", sc), "choices": rec.get("media_type", ""),
                "permalink": rec.get("url", ""), "metrics": m or {},
                "window": label or "",
            })
    except Exception as e:
        log(f"carousel posts unavailable ({type(e).__name__})")
    return out


def _manual_posts(known_shortcodes):
    """Everything on the account the system did NOT publish. One Graph walk,
    bounded, cached in post_metrics state so it costs nothing next tick."""
    out = []
    try:
        import post_metrics, reel_runner
        ps = post_metrics.load_state()
        walked = ps.setdefault("manual", {})
        if not walked.get("_walked_at") or "--rewalk" in __import__("sys").argv:
            got, after = [], None
            while len(got) < MANUAL_WALK_LIMIT:
                params = {"fields": "id,permalink,timestamp,media_type,caption",
                          "limit": min(50, MANUAL_WALK_LIMIT - len(got))}
                if after:
                    params["after"] = after
                r = post_metrics._get(f"{reel_runner.IG_USER_ID}/media", params)
                got.extend(r.get("data", []))
                after = (r.get("paging") or {}).get("cursors", {}).get("after")
                if not (r.get("paging") or {}).get("next"):
                    break
            for it in got:
                sc = shortcode(it.get("permalink"))
                if sc:
                    walked[sc] = {"media_id": it.get("id"), "url": it.get("permalink"),
                                  "timestamp": it.get("timestamp", ""),
                                  "media_type": it.get("media_type", ""),
                                  "caption": (it.get("caption") or "")[:80]}
            walked["_walked_at"] = datetime.now().isoformat(timespec="minutes")
            post_metrics.save_state(ps)
            log(f"walked the account: {len(got)} post(s)")
        for sc, rec in walked.items():
            if sc.startswith("_") or sc in known_shortcodes:
                continue
            out.append({
                "lane": "manual", "posted": rec.get("timestamp", "")[:16].replace("T", " "),
                "what": rec.get("caption", "").split("\n")[0][:70] or rec.get("media_type", ""),
                "choices": rec.get("media_type", ""), "permalink": rec.get("url", ""),
                "metrics": {}, "window": "",
            })
    except Exception as e:
        log(f"manual posts unavailable ({type(e).__name__}: {str(e)[:80]})")
    return out


def all_posts():
    posts = _reel_posts() + _carousel_posts()
    known = {shortcode(p["permalink"]) for p in posts}
    posts += _manual_posts(known)
    posts.sort(key=lambda p: p.get("posted", ""))
    return posts


def _row(n, p):
    m = p.get("metrics") or {}
    v = lambda k: "" if m.get(k) is None else m.get(k)
    return [n, p["lane"], p["posted"], p["what"], p["choices"], p["permalink"],
            v("views"), v("reach"), v("likes"), v("comments"), v("shares"),
            v("saved"), p.get("window", "")]


# ── mirror ──────────────────────────────────────────────────────────────────

def mirror():
    """Upsert every known post. A-M only; N/O untouched. Never raises.
    Returns (added, updated)."""
    try:
        ws = _open()
        rows = ws.get_all_values()
        if not rows:
            ws.update(values=[HEADERS], range_name="A1", value_input_option="RAW")
            rows = [HEADERS]
        by_key = {}
        for i, r in enumerate(rows[1:], start=2):
            k = shortcode(r[PERMALINK_COL] if len(r) > PERMALINK_COL else "")
            if k:
                by_key[k] = (i, r)
        added = updated = 0
        next_n = len(rows)
        for p in all_posts():
            k = shortcode(p["permalink"])
            if not k:
                continue
            if k in by_key:
                i, old = by_key[k]
                new = _row(old[0] if old and old[0] else i - 1, p)
                cur = (old + [""] * WRITTEN_COLS)[:WRITTEN_COLS]
                if [str(x) for x in new] != [str(x) for x in cur]:
                    diff = [HEADERS[j] for j in range(WRITTEN_COLS)
                            if str(new[j]) != str(cur[j])]
                    ws.update(values=[new], range_name=f"A{i}:M{i}",
                              value_input_option="RAW")
                    log(f"  row {i} ({p['lane']}): {', '.join(diff)} changed")
                    updated += 1
            else:
                ws.append_row(_row(next_n, p), value_input_option="RAW",
                              table_range="A1:M1")
                next_n += 1
                added += 1
        if added or updated:
            log(f"mirror: {added} added, {updated} updated")
        return added, updated
    except Exception as e:
        log(f"WARNING: mirror failed ({type(e).__name__}: {str(e)[:100]}) — "
            f"posts are unaffected")
        return 0, 0


# ── read-back ───────────────────────────────────────────────────────────────

def _rating(value):
    v = (value or "").strip().split("/")[0].strip()
    try:
        r = float(v)
        return r if 1 <= r <= 5 else None
    except ValueError:
        return None


def read_feedback():
    """[{key, lane, when, what, choices, rating, note}] from N/O.
    Returns None if the sheet was unreachable. Never raises."""
    try:
        rows = _open().get_all_values()
    except Exception as e:
        log(f"sheet unreadable ({type(e).__name__})")
        return None
    out = []
    for r in rows[1:]:
        r = (r + [""] * len(HEADERS))[:len(HEADERS)]
        link = r[PERMALINK_COL].strip()
        note, rating = r[NOTES_COL].strip(), _rating(r[RATING_COL])
        if not link or (not note and rating is None):
            continue
        out.append({"key": link, "lane": r[1].strip() or "manual",
                    "when": r[2].strip()[:10], "what": r[3].strip(),
                    "choices": r[4].strip(), "rating": rating, "note": note})
    return out


def read_taste_rows():
    """(items, unseen_row_numbers) from the Taste Notes tab, or (None, [])."""
    try:
        rows = _open(TASTE_TAB).get_all_values()
    except Exception as e:
        log(f"Taste Notes unreadable ({type(e).__name__})")
        return None, []
    items, unseen = [], []
    for i, r in enumerate(rows[1:], start=2):
        r = (r + [""] * 4)[:4]
        if not r[1].strip():
            continue
        if not r[3].strip():
            unseen.append(i)
        items.append({"date": r[0].strip(), "note": r[1].strip(),
                      "scope": r[2].strip() or "all"})
    return items, unseen


def stamp_seen(row_numbers):
    if not row_numbers:
        return 0
    try:
        ws = _open(TASTE_TAB)
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        for i in row_numbers:
            ws.update(values=[[stamp]], range_name=f"D{i}",
                      value_input_option="RAW")
        return len(row_numbers)
    except Exception as e:
        log(f"could not stamp Seen ({type(e).__name__})")
        return 0


# ── setup ───────────────────────────────────────────────────────────────────

def setup():
    """Headers, freeze, widths, tints, dropdowns on both tabs. Safe to re-run."""
    ws = _open()
    ws.update(values=[HEADERS], range_name="A1", value_input_option="RAW")
    ss = ws.spreadsheet if hasattr(ws, "spreadsheet") else None
    tws = _open(TASTE_TAB)
    tws.update(values=[TASTE_HEADERS], range_name="A1", value_input_option="RAW")
    if ss is None:
        from google_services import get_sheets_client
        ss = get_sheets_client().open_by_key(SHEET_ID)
    tint = {"red": 0.98, "green": 0.96, "blue": 0.90}
    head = {"red": 0.93, "green": 0.93, "blue": 0.91}

    def base(sid, widths):
        req = [
            {"updateSheetProperties": {"properties": {"sheetId": sid,
                "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount"}},
            {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1},
                "cell": {"userEnteredFormat": {"textFormat": {"bold": True},
                                               "backgroundColor": head}},
                "fields": "userEnteredFormat(textFormat,backgroundColor)"}},
            {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 1},
                "cell": {"userEnteredFormat": {"verticalAlignment": "TOP"}},
                "fields": "userEnteredFormat.verticalAlignment"}},
        ]
        for i, w in enumerate(widths):
            req.append({"updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "COLUMNS",
                          "startIndex": i, "endIndex": i + 1},
                "properties": {"pixelSize": w}, "fields": "pixelSize"}})
        return req

    req = base(ws.id, [46, 90, 118, 380, 200, 230, 70, 70, 64, 84, 68, 64, 130, 70, 320])
    for col in (3, 14):          # D What, O Notes wrap
        req.append({"repeatCell": {"range": {"sheetId": ws.id, "startRowIndex": 1,
                    "startColumnIndex": col, "endColumnIndex": col + 1},
                    "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}},
                    "fields": "userEnteredFormat.wrapStrategy"}})
    for col in (RATING_COL, NOTES_COL):
        req.append({"repeatCell": {"range": {"sheetId": ws.id, "startRowIndex": 0,
                    "startColumnIndex": col, "endColumnIndex": col + 1},
                    "cell": {"userEnteredFormat": {"backgroundColor": tint}},
                    "fields": "userEnteredFormat.backgroundColor"}})
    req.append({"setDataValidation": {"range": {"sheetId": ws.id, "startRowIndex": 1,
                "endRowIndex": 500, "startColumnIndex": RATING_COL,
                "endColumnIndex": RATING_COL + 1},
                "rule": {"condition": {"type": "ONE_OF_LIST",
                         "values": [{"userEnteredValue": str(n)} for n in (1, 2, 3, 4, 5)]},
                         "strict": False, "showCustomUi": True}}})
    treq = base(tws.id, [110, 520, 130, 140])
    treq.append({"repeatCell": {"range": {"sheetId": tws.id, "startRowIndex": 1,
                 "startColumnIndex": 1, "endColumnIndex": 2},
                 "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}},
                 "fields": "userEnteredFormat.wrapStrategy"}})
    treq.append({"setDataValidation": {"range": {"sheetId": tws.id, "startRowIndex": 1,
                 "endRowIndex": 200, "startColumnIndex": 2, "endColumnIndex": 3},
                 "rule": {"condition": {"type": "ONE_OF_LIST",
                          "values": [{"userEnteredValue": v} for v in
                                     ("all", "reels", "images", "educational")]},
                          "strict": False, "showCustomUi": True}}})
    ss.batch_update({"requests": req + treq})
    print(f"Posted Content sheet ready: {SHEET_URL}")
    print("Posts tab: A-M written by the lanes; N Rating (1-5) and O Notes are yours.")
    print("Taste Notes tab: Date | Note | Applies to | Seen.")


if __name__ == "__main__":
    import sys
    if "--setup" in sys.argv:
        setup()
    if "--mirror" in sys.argv or "--rewalk" in sys.argv:
        a, u = mirror()
        print(f"{a} added, {u} updated")
    if "--feedback" in sys.argv:
        for it in read_feedback() or []:
            print(it)
    if len(sys.argv) == 1:
        print(f"posted_sheet {VERSION} — {SHEET_URL}\n"
              f"--setup · --mirror · --rewalk (re-walk the account) · --feedback")
