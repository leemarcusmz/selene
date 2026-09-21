"""
reel_runner.py — the trial-reel lane, end to end
=============================================================================
VERSION 1.18 — 2026-09-16

WHAT IT DOES
    Marcus puts a video in Drive "05. Video Reel / 01. Video Content" (from his
    phone, from anywhere) or drops one into the local
    "03. Content/04. Trial Reels/00. Drop Here/". Nothing else. This picks it up on its own schedule, looks at it, writes a
    caption in the reel routing, and publishes it to Instagram as a TRIAL
    REEL — non-followers only, never on the grid, never on his followers'
    feeds. No approval step exists anywhere in this file, by request.

WHY IT HAS NO GOOGLE SHEET
    The carousel lane's sheet exists because a human approves rows on a review
    screen. This lane has no human step, so a sheet would be a second source of
    truth with nothing to say. State lives in _state/reels.json, which also
    means the lane keeps working when Sheets credentials lapse.

THE ONE THING MARCUS STILL DOES
    Graduating. graduation_strategy is MANUAL, so a trial NEVER reaches his
    followers unless he chooses it in the app after seeing the numbers.
    Changing this to SS_PERFORMANCE would let Instagram push a video he never
    picked to his real audience. Do not change it without asking him.

HOW A VARIANT DIFFERS FROM A REPOST
    A REPOST is the same video with the same hook, and is what the long
    REPOST_COOLDOWN_DAYS guards. A VARIANT is the same footage carrying a
    different hook, which is a genuinely different post and is what this lane
    is for. Variants are what generate the comparison Marcus actually wants:
    same footage, one thing changed, results side by side.

DUPLICATE CONTENT
    Instagram is documented to suppress near-identical video across trials.
    Marcus has not seen this on his own account and asked to allow reposting,
    so it is allowed but BOUNDED: REPOST_COOLDOWN_DAYS between runs of the same
    file and MAX_RUNS_PER_VIDEO in total. If second runs come back with much
    lower views than first runs, that is the suppression showing up and the
    cooldown should go up, not away. run_report() prints exactly that comparison.

CLI
    python3 reel_runner.py --status          # what is in the pool, what is due
    python3 reel_runner.py --dry-run         # full chain, stops before publishing
    python3 reel_runner.py --run             # publish one if one is due
    python3 reel_runner.py --run --force     # ignore the cadence window
    python3 reel_runner.py --only NAME       # target one file by filename
    python3 reel_runner.py --doctor          # check every dependency
    python3 reel_runner.py --feedback        # what Marcus's notes/ratings
                                             # are telling the writers
    python3 reel_runner.py --taste           # push taste/ to the memory repo now
    python3 reel_runner.py --post-metrics    # read carousel results back now

CHANGELOG
    1.18 2026-09-16  ORDERING BUG. eligible_videos() sorted never-posted
                     videos by PATH, so the numbered NZ clips ("1. Mount",
                     "10. Drone"...) — all 16:9 — were always first and the
                     37 vertical clips never got a turn. Marcus: "why only
                     the horizontal videos?" Never-posted videos are now
                     shuffled per tick; posted ones really are longest-
                     rested first, as the comment always claimed.
    1.17 2026-09-16  POSTED CONTENT SHEET mirrored every tick after the
                     carousel metrics pass (posted_sheet.mirror, fail-open),
                     so every post of every lane has a row Marcus can rate.
                     --posted forces a mirror.
    1.16 2026-09-16  taste_brief.maybe_distill() on the tick (weekly, stamped)
                     so a missed Monday screening still refreshes the brief.
                     --brief prints what every writer now receives.
    1.15 2026-09-16  THE TASTE LAYER rides this tick. Two more fail-open
                     passes after the feedback sync: post_metrics reads
                     carousel results back (image + educational lanes, same
                     72h/7d windows as reels), and taste_store pushes
                     taste/{references,feedback,outcomes}.md to the memory
                     repo at most every 6h. This tick hosts them because it
                     is the one always-on process holding the IG token; a
                     failure in either cannot touch a publish. --taste
                     forces a sync; --post-metrics reads carousels now.
    1.14 2026-09-16  FEEDBACK LOOP (reel_feedback.py). Every tick reads
                     Marcus's Notes + Rating from the Trial Reels tab and
                     the new Taste Notes tab, keeps them in reels.json and
                     hands them to the hook and caption writers. Fail-open
                     like metrics and the control tab: a dead sheet means
                     the LAST feedback read, and the reel publishes anyway.
                     Feedback changes HOW a reel is written, never WHETHER.
                     --feedback prints the block; --doctor checks the tab.
    1.13 2026-09-11  MUSIC STATE IS SAVED. The tick saved state only when
                     reel_drive reported a new VIDEO:

                         new, _ = reel_drive.sync(state)
                         reel_music.sync(state)
                         if new:
                             save_state(state)

                     reel_music.sync mutates state["music"], so tracks added on
                     a tick with no new video were downloaded to disk and their
                     records thrown away — and re-downloaded on the next tick,
                     and the one after, forever. 33 Artlist tracks is 222 MB
                     every 15 minutes. It survived today only because Marcus
                     happened to add videos and music in the same window.
                     State is now saved whenever EITHER changed.
    1.12 2026-09-11  --index. The Videos control tab only ever gained a row
                     when a video was PUBLISHED, so at one post per 40 hours
                     the twelve New Zealand clips would have taken three weeks
                     to become settable. The tab existed to be filled in ahead
                     of time and could not be. --index walks the pool and
                     writes a row for every video now: dimensions, measured
                     audio, product from the filename, and the framing the lane
                     would choose. No vision pass, no publishing, no cost.
    1.11 2026-09-11  FRAMING. Non-vertical footage is composed onto a 9:16
                     canvas here, at publish time, rather than converted into a
                     second set of files. The originals stay the only copy, and
                     the treatment stays a decision that can be changed and
                     re-tested. When a clip is fitted, the hook moves into the
                     brand field above the footage instead of sitting on it.
    1.10 2026-09-11  The music decision is now made ONCE, here, and passed to
                     reel_music rather than re-derived there. The Videos tab's
                     "Audio in video? = no" was being ignored on any clip with
                     faint audio. See reel_music 1.1.
    1.9  2026-09-11  --metrics-now now takes a PROBE reading rather than
                     filling every window with an off-schedule number. See
                     reel_metrics 1.1: the first real use of the override broke
                     the comparability rule the whole module exists to keep.
                     Also --repair-windows, to undo a probe that was already
                     written into a window.
    1.8  2026-09-10  METRICS READBACK (reel_metrics.py). Published reels are
                     read back at 72h and 7d and the numbers land in the sheet
                     and in --variants, which until now printed an em-dash and
                     admitted it had nothing. Also fixes a NameError in
                     status(): it referenced `dry_run`, a parameter it does not
                     have, so `--status` crashed. That bug had been shipped and
                     never run — the same class of miss as `Client.auth` and
                     `No module named PIL`, and the reason --doctor now
                     exercises every reporting path rather than importing them.
    1.7  2026-09-10  --doctor now checks Pillow AND the hook font, because both
                     only fail deep inside a run otherwise. The point of doctor
                     is that a missing dependency is found before Marcus starts
                     something, not eleven seconds into it.
    1.6  2026-09-09  FIX: a --dry-run was blocked by the variant cooldown, so
                     after a real publish there was no way to test anything for
                     14 days. A dry run does not record a run and does not
                     consume a variant, so the cooldown should never have
                     applied to it. It now ignores the cooldown (and only the
                     cooldown — retired, rejected and the 3-variant cap still
                     hold, because ignoring those would show output that could
                     never actually publish).
    1.5  2026-09-09  CONTROL TAB DECIDES OVERLAY AND MUSIC. Marcus's rule,
                     replacing the mode rotation:
                       no on-screen text  -> ALWAYS burn the hook in
                       text already there -> NEVER burn one in
                       no audible audio   -> add a licensed track
                       audio already there-> leave it alone
                     Both answers live in the sheet's "Videos" tab, seeded from
                     auto-detection (vision pass for text, loudness for audio)
                     so a video normally needs no editing at all. His override
                     wins when set; an unreachable sheet falls back to detection
                     and the reel still publishes. HOOK_MODE_ROTATION is now
                     only a fallback for when nothing decides.
                     NOTE: this ends the caption-vs-overlay experiment by
                     design — he chose a rule over a measurement.
    1.4  2026-09-09  FILENAME PRODUCT DECLARATION. Naming the product in the
                     Drive filename ("Gauze_Blanket_Soft-Maple.MP4") is taken
                     as ground truth and overrides the vision pass, which
                     honestly could not identify a crinkled cloth on a sofa.
                     Two taps to rename on a phone, so the lane stays
                     upload-and-forget. Applied AFTER the cached description so
                     renaming a file fixes old videos without a new vision call.
    1.3  2026-09-09  DRIVE INTAKE. Videos now come from the Drive folder
                     "05. Video Reel / 01. Video Content" so Marcus can
                     add them from his phone. reel_drive.sync() runs at the top
                     of every tick and downloads anything new into the SAME
                     local drop folder, so nothing downstream changed. The
                     local folder is now a cache, not the source — dropping a
                     file into it by hand still works, and a Drive outage
                     cannot stop videos already in the pool from publishing.
    1.2  2026-09-09  SHEET MIRROR. After a successful publish the run is
                     appended to the "Selene Dreams - Trial Reel" sheet so the
                     hooks and captions are readable without opening JSON.
                     STRICTLY ONE-WAY and FAIL-OPEN: the sheet is never read to
                     make a decision, and a sheet failure is logged but never
                     stops a publish. reels.json remains the only source of
                     truth, which is what lets this lane survive the Google
                     outages that have twice stopped the carousel lane.
    1.1  2026-09-09  HOOK VARIANTS. A source video is now a PARENT that yields
                     up to MAX_VARIANTS_PER_VIDEO runs, each with a different
                     hook, so run-over-run comparison is automatic and every
                     run differs in exactly one thing. Two application modes:
                     "caption" (hook is the caption's first line, video
                     untouched) and "overlay" (hook burned into the opening
                     seconds). DEFAULT IS caption, on evidence — four top
                     bedding reels were opened by hand 2026-09-09 and none
                     burns a text hook. Overlay rotates in as the challenger.
                     Variants use VARIANT_COOLDOWN_DAYS (14) rather than the
                     full repost cooldown, because a new hook is a new post,
                     not a repeat of the old one.
    1.0  2026-09-09  First build.
=============================================================================
"""

import argparse
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import reel_config

VERSION = "1.18"

IG_USER_ID = "17841451177142651"          # @selenedreams_official
GRAPH = "https://graph.facebook.com/v21.0"


# =============================================================================
# LOGGING
# =============================================================================

def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(reel_config.LOG_DIR, exist_ok=True)
        path = os.path.join(reel_config.LOG_DIR,
                            f"reels-{datetime.now().strftime('%Y-%m-%d')}.log")
        with open(path, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


# =============================================================================
# STATE
# =============================================================================

def load_state():
    try:
        with open(reel_config.STATE_PATH) as f:
            return json.load(f)
    except Exception:
        return {"version": VERSION, "videos": {}, "posts": []}


def save_state(state):
    os.makedirs(os.path.dirname(reel_config.STATE_PATH), exist_ok=True)
    tmp = reel_config.STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, reel_config.STATE_PATH)   # atomic: never a half-written file


def file_hash(path):
    """Content hash. Renaming a file does not make it a new video."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


# =============================================================================
# INTAKE
# =============================================================================

def scan_pool():
    """Every usable video in the drop folder, as (path, hash) pairs."""
    if not os.path.isdir(reel_config.DROP_DIR):
        raise RuntimeError(
            f"drop folder does not exist: {reel_config.DROP_DIR}")

    found = []
    for name in sorted(os.listdir(reel_config.DROP_DIR)):
        if name.startswith("."):
            continue
        path = os.path.join(reel_config.DROP_DIR, name)
        if not os.path.isfile(path):
            continue
        if not name.lower().endswith(reel_config.VIDEO_EXTS):
            continue
        found.append((path, file_hash(path)))
    return found


def now_local():
    return datetime.now(ZoneInfo(reel_config.TIMEZONE))


def _parse(ts):
    return datetime.fromisoformat(ts) if ts else None


def eligible_videos(state, pool, ignore_cooldown=False):
    """Which videos may run right now, and why the others may not.

    ignore_cooldown is for DRY RUNS ONLY: a dry run records nothing and
    consumes no variant, so making it wait out a cooldown just means there is
    no way to test the lane for two weeks after a publish.
    """
    ready, blocked = [], []
    now = now_local()

    for path, h in pool:
        rec = state["videos"].get(h, {})
        runs = rec.get("runs", [])
        name = os.path.basename(path)

        if rec.get("retired"):
            blocked.append((name, "retired"))
            continue
        if rec.get("rejected"):
            blocked.append((name, f"rejected: {rec['rejected']}"))
            continue
        if len(runs) >= reel_config.MAX_VARIANTS_PER_VIDEO:
            blocked.append((name, f"all {len(runs)} hook variants used "
                                  f"(max {reel_config.MAX_VARIANTS_PER_VIDEO})"))
            continue
        if runs and not ignore_cooldown:
            last = _parse(runs[-1]["at"])
            # A new hook is a new post, so it waits the shorter variant
            # cooldown. Only an identical re-run would need the long one.
            due = last + timedelta(days=reel_config.VARIANT_COOLDOWN_DAYS)
            if now < due:
                days = max(1, (due - now).days)
                blocked.append((name, f"variant cooldown, {days}d left "
                                      f"({len(runs)} variant(s) run)"))
                continue
        ready.append((path, h, len(runs)))

    # Never-posted first, then longest-rested. Fresh content always wins.
    # Within the never-posted tier the order is RANDOM: sorting by path put
    # the numbered 16:9 clips first every single time (1.18).
    def _rested(r):
        runs = state["videos"].get(r[1], {}).get("runs", [])
        return _parse(runs[-1]["at"]) if runs else None
    fresh = [r for r in ready if r[2] == 0]
    random.shuffle(fresh)
    rested = sorted((r for r in ready if r[2] > 0),
                    key=lambda r: (r[2], _rested(r) or now))
    ready = fresh + rested
    return ready, blocked


def cadence_ok(state, force=False):
    """Is the lane allowed to fire right now? Returns (ok, reason)."""
    if force:
        return True, "forced"

    now = now_local()
    lo, hi = reel_config.POSTING_HOURS
    if not (lo <= now.hour < hi):
        return False, f"outside posting hours {lo}:00-{hi}:00"

    posts = state.get("posts", [])
    if posts:
        last = _parse(posts[-1]["at"])
        gap = (now - last).total_seconds() / 3600
        if gap < reel_config.MIN_HOURS_BETWEEN_POSTS:
            need = reel_config.MIN_HOURS_BETWEEN_POSTS - gap
            return False, f"last trial was {gap:.0f}h ago, {need:.0f}h to go"

    today = [p for p in posts if _parse(p["at"]).date() == now.date()]
    if len(today) >= reel_config.MAX_POSTS_PER_DAY:
        return False, f"daily cap of {reel_config.MAX_POSTS_PER_DAY} reached"

    # Deliberate jitter. A trial that lands at exactly 10:00 every other day is
    # a machine signature; this lane is supposed to look like a person posting.
    if random.random() < 0.35:
        return False, "skipped this tick (cadence jitter)"

    return True, "due"


# =============================================================================
# GRAPH API
# =============================================================================

def ig_token():
    import config
    token = config.IG_ACCESS_TOKEN if hasattr(config, "IG_ACCESS_TOKEN") else None
    if not token:
        token = config._secret("IG_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("IG_ACCESS_TOKEN is not set in .env")
    return token


def _graph(method, path, params):
    url = f"{GRAPH}/{path}"
    payload = dict(params)
    payload["access_token"] = ig_token()
    data = urllib.parse.urlencode(payload).encode()

    if method == "GET":
        req = urllib.request.Request(f"{url}?{data.decode()}", method="GET")
    else:
        req = urllib.request.Request(url, data=data, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:600]
        raise RuntimeError(f"Graph {method} {path} failed ({e.code}): {body}")


def create_trial_reel(video_url, caption):
    """The one call that makes this a TRIAL reel rather than a normal one."""
    trial_params = json.dumps(
        {"graduation_strategy": reel_config.GRADUATION_STRATEGY})
    return _graph("POST", f"{IG_USER_ID}/media", {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "trial_params": trial_params,
    })["id"]


def wait_ready(container_id, tries=60, delay=10):
    """Video containers take far longer than images. Meta transcodes first."""
    for attempt in range(1, tries + 1):
        r = _graph("GET", container_id,
                   {"fields": "status_code,status"})
        code = r.get("status_code")
        if code == "FINISHED":
            return True
        if code == "ERROR":
            raise RuntimeError(f"Meta rejected the video: {r.get('status')}")
        if attempt % 6 == 0:
            log(f"    still transcoding ({code}, {attempt * delay}s elapsed)")
        time.sleep(delay)
    raise RuntimeError(f"container never finished after {tries * delay}s")


def publish_container(container_id):
    return _graph("POST", f"{IG_USER_ID}/media_publish",
                  {"creation_id": container_id})["id"]


def permalink(media_id):
    try:
        return _graph("GET", media_id, {"fields": "permalink"}).get("permalink", "")
    except Exception:
        return ""


# =============================================================================
# THE CHAIN
# =============================================================================

def process(path, h, state, dry_run=False):
    import hook_overlay
    import reel_caption
    import reel_describe
    import reel_hook
    import reel_music
    import reel_products
    import reel_sheet
    import video_host

    name = os.path.basename(path)
    log(f"  video: {name}")

    work_dir = os.path.join(reel_config.WORK_DIR, h)
    shutil.rmtree(work_dir, ignore_errors=True)
    os.makedirs(work_dir, exist_ok=True)

    rec = state["videos"].setdefault(h, {"filename": name, "runs": []})
    rec["filename"] = name

    # 1. validate + prepare -------------------------------------------------
    try:
        prepared, info = video_host.prepare(path, work_dir)
    except ValueError as e:
        # A file that can never work is marked so it is not re-probed forever.
        rec["rejected"] = str(e)
        log(f"  REJECTED: {e}")
        return None
    log(f"  {info['duration']:.1f}s, {info['width']}x{info['height']}, "
        f"{info['bytes'] / 1024 / 1024:.1f} MB")

    # 2. describe (cached — a re-post never pays for vision twice) -----------
    if rec.get("description"):
        description = rec["description"]
        log("  description: cached from an earlier run")
    else:
        description = reel_describe.describe(prepared, info, work_dir)
        rec["description"] = description

    # Ground truth from the filename, applied AFTER the cache so renaming a
    # video in Drive fixes an already-described one without paying for vision
    # again. Marcus naming it beats the model guessing at it.
    # Prefer the DRIVE title over the local cached filename: renaming in Drive
    # is the two-tap phone action, and the local copy keeps whatever name it was
    # downloaded under. Without this, a rename in Drive would never reach here.
    drive_name = next(
        (r.get("name") for r in state.get("drive", {}).values()
         if r.get("local") == name and r.get("name")), None)
    if drive_name and drive_name != name:
        log(f"  drive title: {drive_name}")
    description, declared = reel_products.apply_to_description(
        description, drive_name or name)
    if declared:
        log(f"  product declared by filename: {declared['name']}")
    elif reel_caption.product_is_unclear(description):
        log("  product unclear — rename the file in Drive to declare it "
            "(e.g. Gauze_Blanket_Soft-Maple.mp4)")

    # 3. decide overlay and music -------------------------------------------
    # Detect first, then let Marcus's answers in the control tab override.
    # Detection alone is enough to publish, so a sheet outage changes nothing.
    peak = video_host.measure_loudness(prepared)
    detected = {
        "text": bool(description.get("has_text_overlay")),
        "audio_dbfs": peak,
        "silent": video_host.is_effectively_silent(prepared, info),
    }
    settings = reel_sheet.video_settings(name)

    has_text = settings["text"] if settings["text"] is not None else detected["text"]
    has_audio = (settings["audio"] if settings["audio"] is not None
                 else not detected["silent"])
    src = "sheet" if settings["found"] else "auto-detected"

    # Framing: 9:16 is the screen, not a property of the footage. Decided here
    # so reel_framing only executes, and so the sheet override reaches it.
    import reel_framing
    framing_mode = reel_framing.decide(info, settings.get("framing"))
    framing_meta = None
    if framing_mode != "none":
        framed = os.path.join(work_dir, "framed.mp4")
        try:
            framing_meta = reel_framing.render(prepared, framed, info,
                                               framing_mode)
            prepared = framed
            info = video_host.probe(prepared)
        except Exception as e:
            # Fail-open: publishing a 16:9 reel is worse-looking, not broken.
            log(f"  framing failed ({str(e)[:120]}) — publishing as shot")
            framing_meta = None

    decisions = {"overlay": not has_text, "music": not has_audio,
                 "framing": framing_mode,
                 "framing_note": reel_framing.describe(framing_meta)}
    if framing_mode != "none":
        fsrc = "sheet" if settings.get("framing") else "auto"
        log(f"  framing: {decisions['framing_note']} ({fsrc})")
    log(f"  text in video: {'yes' if has_text else 'no'} ({src}) "
        f"-> overlay {'ON' if decisions['overlay'] else 'OFF'}")
    log(f"  audio in video: {'yes' if has_audio else 'no'} ({src}) "
        f"-> music {'ON' if decisions['music'] else 'OFF'}")

    # 4. hook ---------------------------------------------------------------
    # THE variable under test. Everything else is held as constant as we can.
    variant_index = len(rec["runs"])
    used = [{"hook": r.get("hook"), "pattern_id": r.get("hook_pattern_id")}
            for r in rec["runs"] if r.get("hook")]
    hook, hook_meta = reel_hook.write_hook(
        description, work_dir, variant_index, used=used,
        mode="overlay" if decisions["overlay"] else "caption",
        state=state)
    hook_mode = hook_meta["mode"]

    # 5. overlay (only in overlay mode) --------------------------------------
    publish_path, overlay_meta = prepared, None
    if hook_mode == "overlay":
        dest = os.path.join(work_dir, f"variant_{variant_index + 1}.mp4")
        # A fitted clip has an empty brand field above the footage. Putting the
        # hook there covers nothing and measures 9:1, instead of fighting the
        # footage for legibility.
        band = None
        if framing_meta and framing_meta.get("hook_on_field"):
            band = {"y_frac": framing_meta["hook_y_frac"],
                    "band_frac": framing_meta["hook_band_frac"]}
        overlay_meta = hook_overlay.render(prepared, hook, dest, info,
                                           band=band)
        if overlay_meta is None:
            # The footage cannot carry legible text. Falling back is correct:
            # an unreadable hook is worse than none, and the carousel lane's
            # unfixed pale-photo bug is what happens when you do not check.
            log("  falling back to caption mode for this run")
            hook_mode = "caption"
            hook_meta["mode"] = "caption"
            hook_meta["overlay_refused"] = True
        else:
            # The re-encode changes the file, so re-validate rather than
            # assume the variant still fits Meta's limits.
            new_info = video_host.probe(dest)
            ok, why = video_host.validate(new_info)
            if not ok:
                log(f"  rendered variant fails validation ({why}) — "
                    f"falling back to caption mode")
                hook_mode = "caption"
                hook_meta["mode"] = "caption"
                hook_meta["overlay_refused"] = why
            else:
                publish_path, info = dest, new_info

    # 6. caption ------------------------------------------------------------
    caption, style, meta = reel_caption.write_caption(
        description, work_dir, hook=hook, hook_mode=hook_mode, state=state)
    log(f"  caption ({style}):")
    for line in caption.split("\n"):
        log(f"    | {line}")

    # 7. music ---------------------------------------------------------------
    music_meta = None
    if decisions["music"]:
        # decided=True: this function already combined detection with Marcus's
        # sheet override. reel_music must not second-guess it — see its v1.1.
        publish_path, music_meta = reel_music.maybe_add(
            publish_path, work_dir, info, state, decided=True)

    reel_sheet.upsert_video(
        name, detected, decisions,
        product=(declared or {}).get("name", ""), variants=variant_index + 1)

    if dry_run:
        log("  DRY RUN — stopping before hosting and publishing")
        return {"dry_run": True, "caption": caption, "style": style,
                "hook": hook, "hook_mode": hook_mode,
                "hook_meta": hook_meta, "overlay": overlay_meta,
                "music": music_meta, "decisions": decisions,
                "description": description}

    # 8. host ---------------------------------------------------------------
    slug = f"{datetime.now().strftime('%Y%m%d')}_{h}_v{variant_index + 1}"
    video_url = video_host.host(publish_path, slug)

    # 9. publish ------------------------------------------------------------
    log("  creating trial reel container...")
    container = create_trial_reel(video_url, caption)
    log(f"  container {container} — waiting for Meta to transcode")
    wait_ready(container)
    media_id = publish_container(container)
    url = permalink(media_id)
    log(f"  PUBLISHED as trial reel: {url or media_id}")

    run = {
        "at": now_local().isoformat(timespec="seconds"),
        "variant": variant_index + 1,
        "hook": hook,
        "hook_mode": hook_mode,
        "hook_pattern_id": hook_meta.get("pattern_id"),
        "hook_pattern_name": hook_meta.get("pattern_name"),
        "hook_pattern_strength": hook_meta.get("pattern_strength"),
        "overlay": overlay_meta,
        "music": (music_meta or {}).get("track", ""),
        "media_id": media_id,
        "permalink": url,
        "style": style,
        "caption": caption,
        "seo_phrase": meta.get("seo_phrase_used", ""),
        "prompt_version": meta.get("prompt_version", ""),
        "video_url": video_url,
    }
    rec["runs"].append(run)
    state["posts"].append({"at": run["at"], "hash": h, "media_id": media_id})

    try:
        reel_caption.log_rotation(name, style,
                                  description.get("product_guess", "unclear"))
    except Exception as e:
        log(f"  WARNING: rotation log not written ({e})")

    # Mirror to the sheet. Last, and fail-open: the reel is already live, so
    # nothing here is allowed to raise. reel_sheet swallows its own errors too;
    # this guard is belt and braces because an import error would not be caught
    # inside the module.
    try:
        import reel_sheet
        reel_sheet.append_run(name, run)
    except Exception as e:
        log(f"  WARNING: sheet mirror unavailable ({e}). "
            f"Backfill with: python3 reel_sheet.py --rebuild")

    return run


def run(dry_run=False, force=False, only=None, skip_drive=False):
    state = load_state()

    # Read results back BEFORE anything else in the tick. It is the only part
    # of this function that runs whether or not there is anything to publish,
    # and it must not be skipped just because the pool is empty or the cadence
    # says no — which is exactly when there IS something to read. Fail-open:
    # reel_metrics never raises, so a dead read cannot stop a live post.
    if not dry_run and getattr(reel_config, "METRICS_ON_TICK", True):
        try:
            import reel_metrics
            taken = reel_metrics.pass_over(
                state, limit=getattr(reel_config, "METRICS_MAX_PER_TICK", 6))
            if taken:
                save_state(state)
        except Exception as e:
            log(f"WARNING: metrics readback unavailable ({e}) — "
                f"publishing continues")

    # Read Marcus's feedback. Same shape as metrics: runs on every tick,
    # fail-open, and a dead sheet leaves the last-read feedback in state.
    # Runs on dry runs too, so a --dry-run shows what his notes do.
    if getattr(reel_config, "FEEDBACK_ON_TICK", True):
        try:
            import reel_feedback
            if reel_feedback.sync(state) and not dry_run:
                save_state(state)
        except Exception as e:
            log(f"WARNING: feedback sync unavailable ({e}) — "
                f"publishing continues")

    # Carousel results + the shared taste layer. Both fail-open, both
    # bounded, neither can touch a publish. Skipped on dry runs.
    if not dry_run:
        try:
            import post_metrics
            post_metrics.pass_over()
        except Exception as e:
            log(f"WARNING: carousel metrics unavailable ({e})")
        try:
            import posted_sheet
            posted_sheet.mirror()
        except Exception as e:
            log(f"WARNING: posted sheet mirror unavailable ({e})")
        try:
            import taste_store
            taste_store.maybe_sync()
        except Exception as e:
            log(f"WARNING: taste sync unavailable ({e})")
        try:
            import taste_brief
            taste_brief.maybe_distill()
        except Exception as e:
            log(f"WARNING: taste distill unavailable ({e})")

    # Pull anything new out of Drive FIRST, into the local pool. Fail-open and
    # loud: reel_drive never raises, so a Drive outage still lets whatever is
    # already local publish, but it says so rather than looking like a quiet
    # "nothing due" — the exact silent-failure shape that once killed
    # generation for three days.
    if not skip_drive:
        try:
            import reel_drive
            import reel_music
            new, _ = reel_drive.sync(state)
            # Count music records around the call: reel_music.sync mutates
            # state, and state that is not saved is state that is re-fetched
            # forever. Asking reel_drive whether IT found anything is not a
            # test of whether reel_music did.
            before = len(state.get("music", {}))
            reel_music.sync(state)
            after = len(state.get("music", {}))
            if new or after != before:
                if after != before:
                    log(f"music: {after - before} new track(s), {after} total")
                save_state(state)
        except Exception as e:
            log(f"WARNING: Drive intake unavailable ({e}) — "
                f"continuing with the local pool only")

    pool = scan_pool()
    if not pool:
        log(f"drop folder is empty: {reel_config.DROP_DIR}")
        return

    ready, blocked = eligible_videos(state, pool, ignore_cooldown=dry_run)
    if dry_run and blocked:
        log("dry run: ignoring variant cooldowns (nothing is recorded)")

    if only:
        ready = [r for r in ready if os.path.basename(r[0]) == only]
        if not ready:
            log(f"'{only}' is not eligible right now.")
            for name, why in blocked:
                if name == only:
                    log(f"  reason: {why}")
            return
        force = True

    if not ready:
        log(f"{len(pool)} video(s) in the pool, none eligible:")
        for name, why in blocked:
            log(f"  {name}: {why}")
        return

    ok, why = cadence_ok(state, force=force or dry_run)
    if not ok:
        log(f"not posting: {why} ({len(ready)} video(s) ready)")
        return

    log(f"{len(ready)} eligible, {len(blocked)} blocked")

    # A file that fails validation must not eat the tick. Marcus drops videos
    # without checking codecs, so an unusable file in the pool is normal, not
    # exceptional — the lane steps over it and posts the next one instead.
    for path, h, runs_done in ready:
        log(f"selected {os.path.basename(path)} "
            f"(variant {runs_done + 1} of "
            f"{reel_config.MAX_VARIANTS_PER_VIDEO})")
        try:
            result = process(path, h, state, dry_run=dry_run)
        except Exception as e:
            state["videos"].setdefault(h, {})["last_error"] = str(e)
            state["videos"][h]["last_error_at"] = \
                now_local().isoformat(timespec="seconds")
            save_state(state)
            log(f"  FAILED: {e}")
            log("  video stays in the pool and will be retried on the next tick.")
            return

        if result is not None:
            save_state(state)
            return result

        # process() returned None: the file was rejected as unusable and is now
        # marked so. Persist that and try the next candidate in the same tick.
        save_state(state)
        log("  moving on to the next eligible video")

    log("every eligible video was rejected as unusable — nothing posted")
    return None


def index_pool():
    """Give every video in the pool a row in the Videos tab, without posting.

    Cheap on purpose: ffprobe for dimensions, a loudness measurement for audio,
    the filename for the product, arithmetic for the framing. It deliberately
    does NOT run the vision pass — that costs a model call per video and is the
    one signal that genuinely needs the publish path. "Text in video?" is
    therefore left BLANK for Marcus to answer, which is the honest state: no
    one has looked yet.
    """
    import reel_framing
    import reel_products
    import reel_sheet
    import video_host          # imported inside process() too, not at module level

    state = load_state()
    pool = scan_pool()
    if not pool:
        print(f"\nNothing in {reel_config.DROP_DIR}\n")
        return 0

    print(f"\nIndexing {len(pool)} video(s) into the Videos tab\n")
    done = 0
    seen = set()

    for path, h in sorted(pool, key=lambda p: os.path.basename(p[0])):
        name = os.path.basename(path)
        rec = state["videos"].get(h, {})
        if rec.get("retired"):
            continue
        # Duplicate files share a content hash and therefore one row.
        if h in seen:
            print(f"  {name:<42} duplicate of a clip already indexed")
            continue
        seen.add(h)

        try:
            info = video_host.probe(path)
        except Exception as e:
            print(f"  {name:<42} unreadable ({str(e)[:50]})")
            continue

        peak = video_host.measure_loudness(path)
        silent = video_host.is_effectively_silent(path, info)
        mode = reel_framing.decide(info)
        plan = reel_framing.plan(info, mode) if mode != "none" else None

        drive_name = next(
            (r.get("name") for r in state.get("drive", {}).values()
             if r.get("local") == name and r.get("name")), None)
        declared = reel_products.parse(drive_name or name)

        detected = {"text": None,          # needs the vision pass: left blank
                    "audio_dbfs": peak,
                    "silent": silent}
        decisions = {"overlay": None, "music": not silent is True,
                     "framing": mode,
                     "framing_note": reel_framing.describe(plan)}
        # music mirrors the real rule: added only when there is nothing audible
        decisions["music"] = bool(silent)

        ok = reel_sheet.upsert_video(
            name, detected, decisions,
            product=(declared or {}).get("name", ""),
            variants=len(rec.get("runs", [])))
        done += int(bool(ok))
        print(f"  {name:<42} {info['width']}x{info['height']}  "
              f"{'silent' if silent else f'{peak:.0f} dBFS'}  "
              f"{decisions['framing_note']}")

    print(f"\n{done} row(s) written.\n{reel_config.REEL_SHEET_URL}\n"
          f"\nSet 'Framing' (K) and 'Text in video?' (C) where the lane would "
          f"get it wrong.\n")
    return done


# =============================================================================
# REPORTING
# =============================================================================

def status():
    state = load_state()
    pool = scan_pool()
    # NOT ignore_cooldown=dry_run: status() has no dry_run. It said so as a
    # NameError every time it was called, which is how it was found.
    ready, blocked = eligible_videos(state, pool)
    ok, why = cadence_ok(state)

    print(f"\nTRIAL REEL LANE v{VERSION}")
    print(f"drop folder : {reel_config.DROP_DIR}")
    print(f"pool        : {len(pool)} video(s)")
    print(f"eligible now: {len(ready)}")
    print(f"cadence     : {'DUE' if ok else why}")

    if ready:
        print("\nREADY")
        for path, h, runs in ready:
            print(f"  {os.path.basename(path)}  "
                  f"({'never posted' if not runs else f'{runs} run(s)'})")
    if blocked:
        print("\nHELD")
        for name, w in blocked:
            print(f"  {name}: {w}")

    posts = state.get("posts", [])
    print(f"\ntrials published: {len(posts)}")
    for p in posts[-5:]:
        rec = state["videos"].get(p["hash"], {})
        run = next((r for r in rec.get("runs", [])
                    if r.get("media_id") == p["media_id"]), {})
        print(f"  {p['at'][:16]}  {rec.get('filename', '?')}  "
              f"v{run.get('variant', '?')} [{run.get('hook_mode', '?')}]  "
              f"{run.get('permalink', '')}")
        if run.get("hook"):
            print(f"      hook: {run['hook']}")
    print()


def _views_cell(run):
    """Dash = never read. 'n/a' = read, nothing readable. Else the number."""
    have = run.get("metrics") or {}
    if not have:
        return "\u2014"
    latest = None
    for label, _ in reel_config.METRIC_WINDOWS:
        if label in have:
            latest = have[label]
    if not latest or not latest.get("readable"):
        return "n/a"
    v = latest.get("views", latest.get("reach"))
    return str(v) if v is not None else "n/a"


def variants_report():
    """Same footage, one thing changed, results side by side.

    Views come from reel_metrics as of v1.8. A dash still means "not read yet",
    and "n/a" means read and NOT READABLE — the two are kept apart on purpose,
    because "no data" and "no views" would otherwise look identical and lead to
    opposite conclusions about a hook.
    """
    state = load_state()
    parents = [(h, r) for h, r in state["videos"].items() if r.get("runs")]
    if not parents:
        print("\nNo variants published yet.\n")
        return

    print(f"\nHOOK VARIANTS — {len(parents)} source video(s)\n")
    for h, rec in parents:
        print(f"{rec.get('filename', h)}")
        print(f"  {'#':<3} {'mode':<8} {'pattern':<26} {'views':>7}  hook")
        for r in rec["runs"]:
            print(f"  {r.get('variant', '?'):<3} {r.get('hook_mode', '?'):<8} "
                  f"{(r.get('hook_pattern_name') or '?')[:26]:<26} "
                  f"{_views_cell(r):>7}  {r.get('hook', '')[:52]}")
        print()

    modes, patterns = {}, {}
    for _, rec in parents:
        for r in rec["runs"]:
            modes.setdefault(r.get("hook_mode", "?"), []).append(r)
            patterns.setdefault(r.get("hook_pattern_name", "?"), []).append(r)
    print("SAMPLE SIZES SO FAR (needed before any of this means anything)")
    for m, rs in sorted(modes.items()):
        print(f"  mode {m:<10} {len(rs)} run(s)")
    for pat, rs in sorted(patterns.items()):
        print(f"  {pat[:30]:<32} {len(rs)} run(s)")
    unread = sum(1 for _, rec in parents for r in rec["runs"]
                 if not (r.get("metrics") or {}))
    if unread:
        print(f"\n{unread} run(s) not read back yet \u2014 the first window is "
              f"{reel_config.METRIC_WINDOWS[0][1]}h after publishing.")
    print("\nWith one run per cell none of this means anything yet. The "
          "smallest comparison\nworth reading is one source video posted both "
          "ways, caption and overlay.\n")


def doctor():
    """Check every dependency before Marcus trusts this to run unattended."""
    problems = []

    def check(label, fn):
        try:
            detail = fn()
            print(f"  OK    {label}" + (f" ({detail})" if detail else ""))
        except Exception as e:
            print(f"  FAIL  {label}: {e}")
            problems.append(label)

    print(f"\nTRIAL REEL LANE v{VERSION} — dependency check\n")

    check("drop folder exists", lambda: (
        reel_config.DROP_DIR if os.path.isdir(reel_config.DROP_DIR)
        else (_ for _ in ()).throw(RuntimeError("missing"))))
    check("ffmpeg on PATH", lambda: subprocess.run(
        ["ffmpeg", "-version"], capture_output=True, text=True
    ).stdout.split("\n")[0][:40])
    check("ffprobe on PATH", lambda: subprocess.run(
        ["ffprobe", "-version"], capture_output=True, text=True
    ).stdout.split("\n")[0][:40])
    check("claude CLI on PATH", lambda: shutil.which("claude") or
          (_ for _ in ()).throw(RuntimeError("not found")))

    def _pillow_check():
        try:
            import PIL
        except ImportError:
            raise RuntimeError(
                "not installed for this python — the hook overlay cannot be "
                "drawn. Fix: python3 -m pip install pillow")
        return f"v{PIL.__version__}"

    def _font_check():
        import hook_overlay
        from PIL import ImageFont
        path = hook_overlay.find_font()
        ImageFont.truetype(path, 48)      # prove it actually loads, not just exists
        return os.path.basename(path)

    check("Pillow (hook overlay renderer)", _pillow_check)
    check("hook font loads", _font_check)
    check("github token file", lambda: (
        "present" if os.path.exists(
            os.path.join(reel_config.BASE_DIR, "github_token.txt"))
        else (_ for _ in ()).throw(RuntimeError("missing"))))
    check("IG token reachable", lambda: f"...{ig_token()[-6:]}")
    check("caption-log.md writable", lambda: (
        "present" if os.path.exists(reel_config.CAPTION_LOG_PATH)
        else (_ for _ in ()).throw(RuntimeError(
            f"missing at {reel_config.CAPTION_LOG_PATH}"))))
    check("caption validator importable", lambda: (
        __import__("caption_runner") and "ok"))
    # The two lanes MUST write the same rotation log or the recency filter
    # silently goes blind and every caption collapses into one shape.
    check("rotation log shared with image lane", lambda: (
        "same file" if __import__("caption_runner").CAPTION_LOG_PATH
        == reel_config.CAPTION_LOG_PATH
        else (_ for _ in ()).throw(RuntimeError(
            f"image lane writes {__import__('caption_runner').CAPTION_LOG_PATH}, "
            f"reel lane writes {reel_config.CAPTION_LOG_PATH}"))))
    check("Instagram account reachable", lambda:
          _graph("GET", IG_USER_ID, {"fields": "username"}).get("username"))
    # Mirror only — a failure here is cosmetic, never blocking. Reported so a
    # missing row has an obvious cause rather than being a silent gap.
    check("Trial Reel sheet reachable (mirror only)", lambda: (
        __import__("reel_sheet")._open_tab().title))
    # Optional input. Unreachable = the writers use the last feedback read.
    check("Taste Notes tab reachable (optional input)", lambda: (
        __import__("reel_sheet")._open_tab(reel_config.TASTE_TAB).title))
    check("Posted Content sheet reachable", lambda: (
        __import__("posted_sheet")._open().title))
    check("taste layer collectors run", lambda: (
        f"{len(__import__('taste_store').collect_feedback())} feedback item(s)"))
    check("feedback block renders", lambda: (
        f"{len(__import__('reel_feedback').taste_block(load_state()))} chars"))
    # THE input now. A dead Drive token fails silently everywhere else in this
    # stack, so it gets its own explicit check with the re-auth command.
    def _drive_check():
        import reel_drive
        from google_services import get_drive_service
        vids = reel_drive.list_videos(get_drive_service())
        return "{} video(s)".format(len(vids))

    check("Drive video folder reachable", _drive_check)

    # v1.8: status() shipped with a NameError and nothing caught it, because
    # doctor only ever IMPORTED modules. These CALL the reporting paths with
    # stdout swallowed, so a crash in one is a FAIL here rather than a surprise
    # the next time Marcus types --status.
    def _exercise(fn):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            fn()
        return "runs clean"

    check("--status runs", lambda: _exercise(status))
    check("--variants runs", lambda: _exercise(variants_report))
    check("--metrics runs", lambda: _exercise(
        lambda: __import__("reel_metrics").report()))

    print()
    if problems:
        print(f"{len(problems)} problem(s): {', '.join(problems)}")
        print("The lane will not run reliably until these are fixed.\n")
        return 1
    print("All dependencies present.\n")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Selene Dreams trial reel lane")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--variants", action="store_true",
                    help="hook variants per source video, side by side")
    ap.add_argument("--doctor", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", metavar="FILENAME")
    ap.add_argument("--skip-drive", action="store_true",
                    help="do not sync from Drive this run")
    ap.add_argument("--sync", action="store_true",
                    help="pull new videos from Drive and stop")
    ap.add_argument("--metrics", action="store_true",
                    help="read Instagram results back for published reels")
    ap.add_argument("--posted", action="store_true",
                    help="mirror every published post into the Posted Content sheet now")
    ap.add_argument("--brief", action="store_true",
                    help="print the taste brief every writer receives")
    ap.add_argument("--taste", action="store_true",
                    help="regenerate taste/ in the memory repo and push now")
    ap.add_argument("--post-metrics", action="store_true",
                    help="read carousel results back now (image + edu lanes)")
    ap.add_argument("--feedback", action="store_true",
                    help="sync Marcus's notes/ratings from the sheet and "
                         "print what the writers will see")
    ap.add_argument("--index", action="store_true",
                    help="give every video in the pool a row in the Videos "
                         "tab, without publishing anything")
    ap.add_argument("--repair-windows", action="store_true",
                    help="move any window reading taken before its window was "
                         "reached into the probe slot, so the real reading can "
                         "still happen")
    ap.add_argument("--metrics-now", action="store_true",
                    help="take a PROBE reading now, off schedule \u2014 it is "
                         "recorded separately and does not consume the 72h "
                         "or 7d window")
    args = ap.parse_args()

    if args.doctor:
        sys.exit(doctor())
    if args.variants:
        variants_report()
        return
    if args.index:
        index_pool()
        return
    if args.posted:
        import posted_sheet
        a, u = posted_sheet.mirror()
        print(f"{a} added, {u} updated — {posted_sheet.SHEET_URL}")
        return
    if args.brief:
        import taste_brief
        for stage in taste_brief.STAGE_LANES:
            print(f"\n--- {stage} receives ---\n{taste_brief.brief_block(stage)}")
        return
    if args.taste:
        import taste_store
        ok, msg = taste_store.sync()
        print(("synced: " if ok else "FAILED: ") + msg)
        return
    if args.post_metrics:
        import post_metrics
        s = post_metrics.load_state()
        n = post_metrics.pass_over(s)
        post_metrics.save_state(s)
        print(f"\n{n} reading(s) taken.")
        post_metrics.report(s)
        return
    if args.feedback:
        import reel_feedback
        state = load_state()
        if reel_feedback.sync(state):
            save_state(state)
        reel_feedback.report(state)
        return
    if args.repair_windows:
        import reel_metrics
        state = load_state()
        n = reel_metrics.repair_windows(state)
        if n:
            save_state(state)
            # The sheet still shows the reading under its old window label, so
            # correct it too — otherwise the fix is in state only and the
            # visible copy keeps lying.
            import reel_sheet
            for rec in state.get("videos", {}).values():
                for r in rec.get("runs", []):
                    if r.get("metrics"):
                        try:
                            reel_sheet.write_metrics(r)
                        except Exception as e:
                            log(f"sheet not corrected ({str(e)[:80]})")
        print(f"\n{n} premature window reading(s) moved to the probe slot.")
        reel_metrics.report(state)
        return
    if args.metrics or args.metrics_now:
        import reel_metrics
        state = load_state()
        n = reel_metrics.pass_over(state, force=args.metrics_now)
        if n:
            save_state(state)
        print(f"\n{n} reading(s) taken.")
        reel_metrics.report(state)
        return
    if args.status:
        status()
        return
    if args.sync:
        import reel_drive
        state = load_state()
        new, skipped = reel_drive.sync(state)
        save_state(state)
        print(f"\n{new} new, {skipped} already pulled.\n"
              f"{reel_drive.FOLDER_URL}\n")
        return
    if args.dry_run or args.run or args.only:
        run(dry_run=args.dry_run, force=args.force, only=args.only,
            skip_drive=args.skip_drive)
        return
    status()


if __name__ == "__main__":
    main()
