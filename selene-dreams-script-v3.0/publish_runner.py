"""
publish_runner.py — the last step: actually post to Instagram
=============================================================================
VERSION 1.2 — 2026-08-26

WHAT IT DOES
    Finds every Generation Status row that has been approved on the review
    screen and whose scheduled moment has passed, publishes it to
    @selenedreams_official, and writes the live permalink back into column O.

    That last part matters more than the posting. Column O has never once
    been filled, which is why post-outcomes.csv cannot exist and why "do
    higher-scoring posts actually perform better" has stayed unanswerable.
    Publishing through the API fills it automatically, as a side effect.

HOW IT IS TRIGGERED
    A cron every 15 minutes. POLLING, not sleep-until-time: a timer does not
    survive a reboot, and this runs on a machine that will be rebooted.

CANCELLING
    Column J is re-read IMMEDIATELY before the publish call, not from the
    sweep that selected the row. So changing J away from "Scheduled" any time
    before the post fires cancels it, including seconds beforehand. Once the
    publish call returns, the post is live and can only be removed in the
    Instagram app — there is no unpublish API.

WHAT PROVES THIS WORKS
    The whole call sequence was verified by hand on 2026-08-21 against the
    live account: container -> status -> publish -> permalink. Nothing here
    is speculative except the carousel branch, which follows the same
    documented shape as the single-image one.

CHANGELOG
    1.2  2026-08-26  PRODUCT TAGS: each published slide now carries a
                     shoppable tag for the catalog product matching the
                     queue row's fabric/type/variant (available_catalogs +
                     catalog_product_search). Fail-open: if the catalog is
                     unreachable or nothing matches, the post publishes
                     UNTAGGED and the remark says so — tagging must never
                     block publishing.
    1.1  2026-08-24  --only now reports WHY a named row was skipped instead of
                     printing "nothing due"; image_host trailing-slash fix.
    1.0  2026-08-24  First build.
=============================================================================
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import config
import image_host
from google_services import get_sheets_client, get_drive_service

# ── identity (verified live 2026-08-21) ─────────────────────────────────────
IG_USER_ID = "17841451177142651"          # @selenedreams_official
FB_PAGE_ID = "659765693888211"            # Selene Dreams
GRAPH = "https://graph.facebook.com/v21.0"

# ── schedule ────────────────────────────────────────────────────────────────
# Chosen 2026-08-21: Tue/Thu/Sat, aimed at a US audience.
# The hour is anchored in America/New_York and CONVERTED, never hardcoded in
# HKT — US clocks shift twice a year and a fixed HKT time would silently drift
# the posts an hour away from the audience every March and November.
POST_TZ = ZoneInfo("America/New_York")
POST_HOUR = 21                             # 21:00 ET = 18:00 PT = 09:00 HKT next day
POST_DAYS = (1, 3, 5)                      # Mon=0 ... Tue/Thu/Sat

# ── statuses ────────────────────────────────────────────────────────────────
POST_SCHEDULED = "Scheduled"
POST_DONE = "Done"
POST_HOLD = "Hold"

MAX_CAROUSEL = 10
MIN_CAROUSEL = 2
CONTAINER_POLL_TRIES = 20
CONTAINER_POLL_DELAY = 3


def log(msg):
    print(f"[publish] {msg}", flush=True)


def ig_token():
    """Lazily, so a missing token cannot break every other script at import."""
    tok = config._ENV.get("IG_ACCESS_TOKEN")
    if not tok:
        raise RuntimeError(
            "IG_ACCESS_TOKEN is not in .env. Add a Meta token with "
            "instagram_basic + instagram_content_publish. A Graph API Explorer "
            "token works for testing but expires in ~2 hours; production wants a "
            "Business Manager SYSTEM USER token, which never expires.")
    return tok


# ── Graph API ───────────────────────────────────────────────────────────────

def _graph(method, path, params):
    params = dict(params, access_token=ig_token())
    url = f"{GRAPH}/{path}"
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        url = f"{url}?{urllib.parse.urlencode(params)}"
        data = None
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            err = json.loads(body).get("error", {})
            raise RuntimeError(
                f"{err.get('message', body)} "
                f"(code {err.get('code')}/{err.get('error_subcode')})") from None
        except json.JSONDecodeError:
            raise RuntimeError(f"HTTP {e.code}: {body[:300]}") from None


def create_container(image_url, caption=None, carousel_item=False,
                     product_tags=None):
    params = {"image_url": image_url}
    if carousel_item:
        params["is_carousel_item"] = "true"
    if caption is not None:
        params["caption"] = caption
    if product_tags:
        # [{"product_id": "...", "x": 0.5, "y": 0.82}] — x/y are fractions of
        # the image, the tap target for the shopping tag.
        params["product_tags"] = json.dumps(product_tags)
    return _graph("POST", f"{IG_USER_ID}/media", params)["id"]


def create_carousel(children, caption):
    return _graph("POST", f"{IG_USER_ID}/media", {
        "media_type": "CAROUSEL",
        "children": ",".join(children),
        "caption": caption,
    })["id"]


def wait_ready(container_id):
    """Containers report FINISHED / IN_PROGRESS / ERROR / EXPIRED. Publishing
    an unfinished one fails with an unhelpful message, so wait properly."""
    for _ in range(CONTAINER_POLL_TRIES):
        st = _graph("GET", container_id, {"fields": "status_code,status"})
        code = st.get("status_code", "")
        if code == "FINISHED":
            return True
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container {container_id} is {code}: {st.get('status', '')}")
        time.sleep(CONTAINER_POLL_DELAY)
    raise RuntimeError(f"container {container_id} never reached FINISHED")


def publish(container_id):
    return _graph("POST", f"{IG_USER_ID}/media_publish",
                  {"creation_id": container_id})["id"]


def permalink(media_id):
    return _graph("GET", media_id, {"fields": "permalink"}).get("permalink", "")


# ── product tagging (v1.2) ──────────────────────────────────────────────────
# The shop is already approved (tags work manually in the app), so this only
# needs the token to see the catalog. Everything here FAILS OPEN: any error
# or empty match publishes the post untagged rather than holding it.

PRODUCT_TAGS_ENABLED = True
TAG_X, TAG_Y = 0.5, 0.82        # tap target: centred, low on the image

_catalog_cache = None


def catalog_id():
    global _catalog_cache
    if _catalog_cache is None:
        r = _graph("GET", f"{IG_USER_ID}/available_catalogs",
                   {"fields": "catalog_id,catalog_name"})
        data = r.get("data", [])
        _catalog_cache = data[0]["catalog_id"] if data else ""
    return _catalog_cache


def find_product(fabric, ptype, variant):
    """Best catalog match for this row's product, or None. Never raises.

    Search narrows: exact fabric+type+variant first, then fabric+type, then
    type alone — the first query with results wins, and within results an
    'approved' review_status is preferred (only approved products are
    taggable)."""
    try:
        cid = catalog_id()
        if not cid:
            log("  NOTE: no catalog visible to this token — publishing untagged.")
            return None
        for terms in ((fabric, ptype, variant), (fabric, ptype), (ptype,)):
            q = " ".join(t for t in terms if t).strip()
            if not q:
                continue
            r = _graph("GET", f"{IG_USER_ID}/catalog_product_search",
                       {"catalog_id": cid, "q": q})
            data = r.get("data", [])
            if data:
                approved = [d for d in data
                            if str(d.get("review_status", "")).lower()
                            in ("", "approved")]
                return (approved or data)[0]
    except Exception as e:
        log(f"  NOTE: product lookup failed ({e}) — publishing untagged.")
    return None


# ── sheet access ────────────────────────────────────────────────────────────

def open_tabs():
    gc = get_sheets_client()
    ss = gc.open_by_key(config.GOOGLE_SHEET_ID)
    return ss.worksheet(config.GS_SHEET_NAME), ss.worksheet(config.GOOGLE_SHEET_NAME)


GS_COL_SLIDES = 16          # P — "Approved Slides", written by review.gs


def cell(row, col):
    return (row[col - 1].strip() if len(row) >= col else "")


def note(gs, gs_row, message):
    prev = gs.cell(gs_row, config.GS_COL_SYS_REMARK).value or ""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    gs.update_cell(gs_row, config.GS_COL_SYS_REMARK,
                   (prev + " | " if prev else "") + f"[{stamp}] PUBLISH: {message}")


def scheduled_moment(date_str):
    """Column K holds a date. The hour comes from the schedule policy above,
    in New York time, converted to a real instant."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            d = datetime.strptime(date_str.strip(), fmt)
            break
        except ValueError:
            continue
    else:
        return None
    return datetime(d.year, d.month, d.day, POST_HOUR, tzinfo=POST_TZ)


def next_slot(after=None):
    """The next Tue/Thu/Sat at POST_HOUR ET. Used by --next-slot so the review
    screen and this runner agree on what the cadence means."""
    now = (after or datetime.now(POST_TZ)).astimezone(POST_TZ)
    probe = now
    for _ in range(14):
        if probe.weekday() in POST_DAYS:
            slot = probe.replace(hour=POST_HOUR, minute=0, second=0, microsecond=0)
            if slot > now:
                return slot
        probe = (probe + timedelta(days=1)).replace(hour=0, minute=0)
    return None


# ── one row ─────────────────────────────────────────────────────────────────

def publish_row(gs, queue, gs_row, number, dry_run=False):
    slides_spec = cell(gs.row_values(gs_row), GS_COL_SLIDES)
    q_row = queue.row_values(int(number) + 1)
    image_cell = cell(q_row, config.COL_IMAGE_URLS + 1)
    import re
    all_ids = re.findall(r"/file/d/([A-Za-z0-9_\-]+)", image_cell)
    if not all_ids:
        raise RuntimeError("no Drive image URLs on the queue row")

    if slides_spec:
        wanted = [int(x) for x in slides_spec.split(",") if x.strip().isdigit()]
    else:
        wanted = list(range(1, len(all_ids) + 1))
    ids = [all_ids[i - 1] for i in wanted if 1 <= i <= len(all_ids)]
    if not ids:
        raise RuntimeError(f"approved slides {slides_spec!r} match none of the {len(all_ids)} images")
    if len(ids) > MAX_CAROUSEL:
        raise RuntimeError(f"{len(ids)} slides — Instagram allows at most {MAX_CAROUSEL}")

    caption = caption_for(gs, number)
    log(f"  #{number}: {len(ids)} slide(s) {wanted}, caption {len(caption)} chars")
    if dry_run:
        log("  DRY RUN — stopping before anything is hosted or posted")
        return None, None

    week = datetime.now().strftime("%Y-%m-%d")
    drive = get_drive_service()
    urls = image_host.host_slides(drive, ids, number, week)

    # LAST CHANCE TO CANCEL — re-read J now, not from the earlier sweep.
    live_status = gs.cell(gs_row, config.GS_COL_POST_STATUS).value or ""
    if live_status.strip() != POST_SCHEDULED:
        raise RuntimeError(f"cancelled — Post Status is now {live_status.strip()!r}")

    tags, prod = None, None
    if PRODUCT_TAGS_ENABLED:
        prod = find_product(cell(q_row, config.COL_FABRIC + 1),
                            cell(q_row, config.COL_PRODUCT_TYPE + 1),
                            cell(q_row, config.COL_VARIANT + 1))
        if prod:
            tags = [{"product_id": prod["product_id"], "x": TAG_X, "y": TAG_Y}]
            log(f"  #{number}: tagging product "
                f"{prod.get('product_name') or prod['product_id']}")
        else:
            log(f"  #{number}: no catalog product matched — publishing untagged")
            note(gs, gs_row, "no product tag (no catalog match)")

    def build_containers(t):
        if len(urls) >= MIN_CAROUSEL:
            kids = []
            for u in urls:
                cid = create_container(u, carousel_item=True, product_tags=t)
                wait_ready(cid)
                kids.append(cid)
            return create_carousel(kids, caption)
        return create_container(urls[0], caption=caption, product_tags=t)

    try:
        container = build_containers(tags)
    except Exception as e:
        if not tags:
            raise
        # Fail open: a rejected product_tags call (missing permission, product
        # not taggable) must not hold the post. Rebuild untagged.
        log(f"  NOTE: tagged container rejected ({e}) — retrying untagged.")
        note(gs, gs_row, f"product tag rejected by API ({str(e)[:120]}) — posted untagged")
        prod, tags = None, None
        container = build_containers(None)
    wait_ready(container)

    media_id = publish(container)
    link = permalink(media_id)
    if prod:
        note(gs, gs_row, "tagged "
             + str(prod.get("product_name") or prod["product_id"])[:80])
    elif PRODUCT_TAGS_ENABLED and tags is None and prod is None:
        pass  # untagged reason already noted (no match, lookup failure, or rejection)
    log(f"  #{number} PUBLISHED — {link}")
    return media_id, link


def caption_for(gs, number):
    cap_sheet = gs.spreadsheet.worksheet("Generated Caption")
    for r in cap_sheet.get_all_values()[1:]:
        if r and r[0].strip() == str(number):
            return (r[1] if len(r) > 1 else "").strip()
    return ""


# ── the sweep ───────────────────────────────────────────────────────────────

def run(dry_run=False, only=None, force=False):
    gs, queue = open_tabs()
    rows = gs.get_all_values()
    now = datetime.now(POST_TZ)
    due, published, failed = [], [], []

    for idx, row in enumerate(rows[config.GS_HEADER_ROW:], start=config.GS_HEADER_ROW + 1):
        number = cell(row, config.GS_COL_NUMBER)
        if not number:
            continue
        if only and str(number) != str(only):
            continue
        status = cell(row, config.GS_COL_POST_STATUS)
        if status != POST_SCHEDULED:
            # Silence here is what made "nothing due" look like a bug rather
            # than an un-approved row. If a row was named explicitly, say why.
            if only:
                log(f"#{number}: Post Status is {status or '(blank)'!r}, not "
                    f"{POST_SCHEDULED!r} — approve it on the review link first, "
                    f"or set J manually to test.")
            continue
        when = scheduled_moment(cell(row, config.GS_COL_SCHED_DATE))
        if when is None:
            log(f"#{number}: unreadable Scheduled Date — skipping")
            continue
        if when > now and not force:
            log(f"#{number}: not due until {when:%Y-%m-%d %H:%M %Z}")
            continue
        due.append((idx, number))

    if not due:
        log("nothing due.")
        return 0

    log(f"{len(due)} post(s) due.")
    for gs_row, number in due:
        try:
            media_id, link = publish_row(gs, queue, gs_row, number, dry_run=dry_run)
            if dry_run:
                continue
            gs.update_cell(gs_row, config.GS_COL_POST_URL, link)
            gs.update_cell(gs_row, config.GS_COL_POST_STATUS, POST_DONE)
            note(gs, gs_row, f"published, media {media_id}")
            published.append(number)
        except Exception as e:
            msg = str(e)
            log(f"  #{number} FAILED: {msg}")
            failed.append(number)
            try:
                # Hold rather than leaving it Scheduled: a row that keeps
                # failing would otherwise retry every 15 minutes forever.
                if not msg.startswith("cancelled"):
                    gs.update_cell(gs_row, config.GS_COL_POST_STATUS, POST_HOLD)
                note(gs, gs_row, msg[:300])
            except Exception:
                pass

    log(f"done — {len(published)} published, {len(failed)} failed.")
    return 0 if not failed else 1


def main():
    p = argparse.ArgumentParser(description="Publish approved Selene posts to Instagram")
    p.add_argument("--dry-run", action="store_true",
                   help="resolve slides and caption, host nothing, post nothing")
    p.add_argument("--only", help="a single Generation Status #")
    p.add_argument("--force", action="store_true",
                   help="ignore the scheduled time and publish now")
    p.add_argument("--next-slot", action="store_true",
                   help="print the next Tue/Thu/Sat slot and exit")
    a = p.parse_args()
    if a.next_slot:
        s = next_slot()
        print(s.strftime("%Y-%m-%d %H:%M %Z"), "=",
              s.astimezone(ZoneInfo("Asia/Hong_Kong")).strftime("%Y-%m-%d %H:%M HKT"))
        return 0
    return run(dry_run=a.dry_run, only=a.only, force=a.force)


if __name__ == "__main__":
    sys.exit(main())
