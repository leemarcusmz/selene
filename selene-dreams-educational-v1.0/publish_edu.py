# =============================================================================
# publish_edu.py — schedule and publish approved educational carousels
# VERSION 1.1 — 2026-09-16
# CHANGELOG
#   1.1  2026-09-16  Honours Generation Status col P "Approved Slides" (written
#                    by review.gs v2.5 on approve): '3,1,2' = publish those
#                    slides, in that order, 1-based into the queue's col Q list.
#                    Blank or unparsable P = every slide in Q order, exactly as
#                    1.0 did. Out-of-range numbers are ignored; fewer than
#                    MIN_CAROUSEL survivors -> error -> K=Hold, as before.
#                    sheets_edu.status_rows() now returns 'slides' (col P).
#   1.0  2026-09-09  First release. Two passes every tick:
#                    SCHEDULE: K=Approved with L blank -> the next free Thursday
#                      21:00 New York (Marcus's fixed-day call; day is config),
#                      never doubling up on a Thursday another edu row holds.
#                      Writes L=date, K=Scheduled.
#                    FIRE: K=Scheduled whose L slot has passed -> re-read K as
#                      the last chance to cancel -> host slides through v3.0's
#                      image_host (posts/edu/<week>/...) which also strips the
#                      AI-provenance metadata -> Meta carousel via v3.0's
#                      publish primitives -> K=Posted, M=date, permalink written
#                      to the queue's Carousel-ID and to Post Topic's Post url,
#                      topic Status -> Posted. NO product tags (Marcus: caption
#                      only). Failures park at K=Hold with the error in col N.
#                    Everything from v3.0 is IMPORTED; publish_runner.py is
#                    untouched and the image lane's schedule is unaffected.
# =============================================================================
import datetime
from zoneinfo import ZoneInfo
import config_edu as C
import sheets_edu as S
import library_edu as L
from caption_edu import drive_ids
from notify_edu import caption_for

# v3.0, read-only
import image_host
from publish_runner import create_container, create_carousel, wait_ready, publish, permalink

TZ = ZoneInfo(C.POST_TZ_NAME)
MIN_CAROUSEL = 2


from log_edu import log


def slot_moment(date_str):
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            d = datetime.datetime.strptime(date_str.strip(), fmt); break
        except ValueError:
            continue
    else:
        return None
    return datetime.datetime(d.year, d.month, d.day, C.POST_HOUR, tzinfo=TZ)


def next_free_slot(taken_dates, after=None):
    """Next POST_WEEKDAY at POST_HOUR (NY) strictly after now, skipping dates
    another educational row already holds."""
    now = (after or datetime.datetime.now(TZ)).astimezone(TZ)
    probe = now
    for _ in range(120):
        if probe.weekday() == C.POST_WEEKDAY:
            slot = probe.replace(hour=C.POST_HOUR, minute=0, second=0, microsecond=0)
            if slot > now and slot.strftime("%Y-%m-%d") not in taken_dates:
                return slot
        probe = (probe + datetime.timedelta(days=1)).replace(hour=0, minute=0)
    return None


def schedule():
    n = 0
    rows = S.status_rows()
    taken = {r["sched"].strip() for r in rows if r["post"] in (C.POST_SCHEDULED, C.POST_POSTED) and r["sched"].strip()}
    for st in rows:
        if st["post"] != C.POST_APPROVED or st["sched"].strip():
            continue
        slot = next_free_slot(taken)
        if not slot:
            continue
        date = slot.strftime("%Y-%m-%d"); taken.add(date)
        S.set_status(st["row"], "L", date)
        S.set_status(st["row"], "K", C.POST_SCHEDULED)
        S.add_remark(st["row"], "SCHEDULE",
                     f"{slot.strftime('%a %Y-%m-%d %H:%M')} New York · change K to cancel")
        log(f"schedule #{st['num']} -> {date}")
        n += 1
    return n


def pick_slides(ids, approved):
    """v1.1 — apply review.gs's 'Approved Slides' (e.g. '3,1,2', 1-based, in
    publish order) to the queue's slide list. Blank -> all, unchanged."""
    order = []
    for tok in str(approved or "").split(","):
        tok = tok.strip()
        if tok.isdigit() and 1 <= int(tok) <= len(ids) and int(tok) not in order:
            order.append(int(tok))
    if not order:
        return ids
    log(f"  approved slides {order} of {len(ids)}")
    return [ids[i - 1] for i in order]


def publish_row(st, dry_run=False):
    number = st["num"]
    q = next((x for x in S.queue_rows() if str(x["num"]) == str(number)), None)
    if not q:
        raise RuntimeError("queue row not found")
    ids = drive_ids(q["urls"])
    ids = pick_slides(ids, st.get("slides", ""))
    if len(ids) < MIN_CAROUSEL:
        raise RuntimeError(f"{len(ids)} slide(s) — a carousel needs at least {MIN_CAROUSEL}")
    caption = caption_for(number)
    if not caption.strip():
        raise RuntimeError("no caption in the Generated Caption tab")
    log(f"  #{number}: {len(ids)} slides, caption {len(caption)} chars")
    if dry_run:
        return None, "(dry run)"
    week = f"edu/{datetime.datetime.now().strftime('%Y-%m-%d')}"   # posts/edu/<date>/row<N>_slide<i>.jpg
    urls = image_host.host_slides(L.drive(), ids, number, week)

    # LAST CHANCE TO CANCEL — re-read K now.
    live = S.tab(C.TAB_STATUS).acell(f"K{st['row']}").value or ""
    if live.strip() != C.POST_SCHEDULED:
        raise RuntimeError(f"cancelled — Post-Status is now {live.strip()!r}")

    kids = []
    for u in urls:
        cid = create_container(u, carousel_item=True)     # no product tags on this lane
        wait_ready(cid); kids.append(cid)
    container = create_carousel(kids, caption)
    wait_ready(container)
    media_id = publish(container)
    link = permalink(media_id)
    log(f"  #{number} PUBLISHED — {link}")
    return media_id, link


def fire(dry_run=False):
    n = 0
    now = datetime.datetime.now(TZ)
    topics = {str(t["num"]): t for t in S.topics_rows()}
    for st in S.status_rows():
        if st["post"] != C.POST_SCHEDULED:
            continue
        when = slot_moment(st["sched"])
        if not when or when > now:
            continue
        try:
            media_id, link = publish_row(st, dry_run=dry_run)
            if dry_run:
                log(f"  DRY RUN #{st['num']} would publish now"); continue
            S.set_status(st["row"], "K", C.POST_POSTED)
            S.set_status(st["row"], "M", now.strftime("%Y-%m-%d"))
            S.add_remark(st["row"], "PUBLISH", f"posted {link}")
            q = next((x for x in S.queue_rows() if str(x["num"]) == str(st["num"])), None)
            if q:
                S.tab(C.TAB_QUEUE).update_acell(f"R{q['row']}", link)
                t = topics.get(str(q["topic"]))
                if t:
                    ws = S.topic_sheet().worksheet(C.TAB_TOPICS)
                    ws.update_acell(f"L{t['row']}", link)
                    ws.update_acell(f"K{t['row']}", "Posted")
            n += 1
        except Exception as e:
            S.set_status(st["row"], "K", C.POST_HOLD)
            S.add_remark(st["row"], "PUBLISH", f"ERROR: {e}")
            log(f"publish #{st['num']} ERROR: {e}")
    return n


def run(dry_run=False):
    s = schedule()
    p = fire(dry_run=dry_run)
    return f"{s} scheduled, {p} published"


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--next-slot", action="store_true", help="print the next free slot and exit")
    a = ap.parse_args()
    if a.next_slot:
        rows = S.status_rows()
        taken = {r["sched"].strip() for r in rows if r["sched"].strip()}
        print(next_free_slot(taken))
    else:
        print(run(dry_run=a.dry_run))
