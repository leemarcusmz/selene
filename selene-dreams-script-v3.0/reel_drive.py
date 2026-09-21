"""
reel_drive.py — pull new videos out of Google Drive into the local pool
=============================================================================
VERSION 1.5 — 2026-09-11

WHY DRIVE IS THE SOURCE NOW
    Marcus wanted to add videos from anywhere, including his phone. The local
    drop folder needs him sitting at the Mac. So the Drive folder
    "10. AI Generation / 05. Video Reel / 01. Video Content" is the input, and
    this module syncs it down. That folder is deliberately generic rather than
    trial-reel specific, so other flows can draw on the same footage.

THE DESIGN, DELIBERATELY BORING
    This does not replace the intake. It FEEDS it. New Drive files are
    downloaded into the same local drop folder the lane already scans, so
    everything downstream — hashing, validation, variants, cooldown, cadence —
    is completely unchanged and still works if Drive is unreachable. The local
    folder becomes a cache rather than the source, and dropping a file there by
    hand still works exactly as before.

    That also means a video is downloaded ONCE and then reused across all its
    hook variants, instead of being re-fetched every run.

OAUTH, NOT THE SERVICE ACCOUNT
    Recorded lesson: service accounts for Sheets, OAuth for Drive, because
    service accounts have no Drive quota. This uses the same
    get_drive_service() / download_file_from_drive() the image lane uses.

    THE KNOWN FAILURE MODE: a dead Drive OAuth token killed generation once and
    did it SILENTLY — status stayed Ready, no ERROR, no remark
    (selene-oauth-token-dead). So every failure here is LOUD: it names the
    token file and the exact re-auth command. A quiet Drive failure would mean
    Marcus uploads videos and simply nothing ever happens, which is the worst
    possible behaviour for a lane whose whole promise is "drop it and forget".

CHANGELOG
    1.5  2026-09-11  A LOCK. The 15-minute tick and a manual `--sync` are two
                     processes pointed at the same Drive folder and the same
                     drop folder. Run together, each downloads what the other
                     has not yet recorded, and the collision-avoidance rename
                     turns the second copy into "8. Sheep + pillows_2.mp4".
                     That is how 12 clips became 21 on 2026-09-11: half a
                     gigabyte of duplicates. Harmless to publishing — the pool
                     is keyed on CONTENT HASH, so both copies share one record
                     and one cooldown — but wasteful and confusing. Only one
                     sync may now run at a time; the loser says so and returns.
    1.4  2026-09-11  Intake is judged against MAX_SOURCE_BYTES, not the
                     hosting cap. A 4K master downscales before anything is
                     hosted, so refusing to DOWNLOAD it for being too big to
                     HOST threw away usable footage.
    1.3  2026-09-11  SUBFOLDERS ARE NOW SEARCHED. list_videos only ever asked
                     for direct children of "01. Video Content", so the moment
                     Marcus organised the footage into "_New Zealand Shoot /
                     _Horizontal" the lane stopped seeing ANY of it — and said
                     "drop folder is empty", which reads as "nothing new" rather
                     than "I cannot see your files". Folders are now walked
                     recursively, and each video carries the subfolder path it
                     came from so the log and the sheet can say where it lives.
    1.2  2026-09-09  Source folder moved to "05. Video Reel / 01. Video Content"
                     (Marcus restructured Drive so other flows can reuse the
                     footage). The id now comes from the shared config.py.
                     Drive FILE ids are unchanged by a move, so nothing
                     re-downloads and no state migration was needed.
    1.1  2026-09-09  Refresh the stored Drive TITLE on every sync, even when the
                     file is already downloaded. Renaming a video in Drive is
                     how Marcus declares its product (reel_products), and v1.0
                     cached the title at download time and never looked again —
                     so a rename silently did nothing, which is the worst
                     possible outcome for a two-tap action he was told works.
    1.0  2026-09-09  First build.
=============================================================================
"""

import os
import time
import re

import config
import reel_config

FOLDER_ID = config.DRIVE_VIDEO_CONTENT_FOLDER_ID   # 05. Video Reel / 01. Video Content
FOLDER_URL = f"https://drive.google.com/drive/folders/{FOLDER_ID}"

# How many folders deep to look. 3 covers "shoot / orientation / file" with room
# to spare. A cap, not a preference: without one, a folder cycle or a big nested
# archive would turn a 15-minute tick into hundreds of Drive calls.
MAX_FOLDER_DEPTH = 3

VIDEO_MIMES = ("video/mp4", "video/quicktime", "video/x-m4v")

REAUTH_HINT = (
    "The Drive OAuth token is dead or missing. Fix it with:\n"
    "      cd <v3.0 folder> && python3 -c "
    "'from google_services import get_drive_service; get_drive_service()'\n"
    "    That opens the consent flow and rewrites token.json.")


def log(msg):
    print(f"[reel_drive] {msg}", flush=True)


def safe_name(name):
    """Drive titles can contain anything. Keep it a sane local filename."""
    name = os.path.basename(name).strip()
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name)
    return name or "video.mp4"


def _child_folders(drive_service, parent_id):
    """Immediate subfolders of one folder."""
    resp = drive_service.files().list(
        q=(f"'{parent_id}' in parents and trashed = false and "
           f"mimeType = 'application/vnd.google-apps.folder'"),
        spaces="drive", fields="files(id, name)",
        supportsAllDrives=True, includeItemsFromAllDrives=True,
        pageSize=200).execute()
    return resp.get("files", [])


def _videos_in(drive_service, folder_id):
    """Videos directly inside one folder, paged."""
    q = (f"'{folder_id}' in parents and trashed = false and ("
         + " or ".join(f"mimeType = '{m}'" for m in VIDEO_MIMES) + ")")
    files, token = [], None
    while True:
        resp = drive_service.files().list(
            q=q, spaces="drive",
            fields="nextPageToken, files(id, name, mimeType, size, "
                   "modifiedTime)",
            pageToken=token, supportsAllDrives=True,
            includeItemsFromAllDrives=True, pageSize=200).execute()
        files.extend(resp.get("files", []))
        token = resp.get("nextPageToken")
        if not token:
            break
    return files


def list_videos(drive_service, folder_id=None, _rel="", _depth=0):
    """Every video in the folder AND its subfolders.

    Recursive since v1.3. Marcus organises footage into shoot folders
    ("_New Zealand Shoot / _Horizontal"), and a flat listing simply did not
    see them — the lane reported an empty pool, which is indistinguishable
    from "nothing new to post". Depth is capped so a stray folder loop or a
    deeply nested archive cannot turn one tick into hundreds of API calls.

    Each file gains "rel_path": the subfolder it came from, "" at the top.
    """
    folder_id = folder_id or FOLDER_ID
    files = _videos_in(drive_service, folder_id)
    for f in files:
        f["rel_path"] = _rel

    if _depth >= MAX_FOLDER_DEPTH:
        if files or _rel:
            log(f"not descending past {_rel or '/'} "
                f"(depth cap {MAX_FOLDER_DEPTH})")
        return files

    for sub in _child_folders(drive_service, folder_id):
        files.extend(list_videos(
            drive_service, sub["id"],
            _rel=f"{_rel}/{sub['name']}".lstrip("/"), _depth=_depth + 1))
    return files


LOCK_PATH = os.path.join(reel_config.BASE_DIR, "_state", "drive-sync.lock")
LOCK_STALE_SECONDS = 20 * 60      # longer than any real sync; a crash self-heals


class _Lock:
    """One sync at a time. Never raises, never blocks forever.

    A stale lock (a crashed run) expires on its own rather than needing a
    human to delete a file — an unattended lane must not be stoppable by
    leftover state.
    """

    def __init__(self):
        self.held = False

    def __enter__(self):
        try:
            os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
            if os.path.exists(LOCK_PATH):
                age = time.time() - os.path.getmtime(LOCK_PATH)
                if age < LOCK_STALE_SECONDS:
                    return self
                log(f"clearing a stale sync lock ({age / 60:.0f} min old)")
            with open(LOCK_PATH, "w") as f:
                f.write(str(os.getpid()))
            self.held = True
        except Exception:
            # If locking itself fails, proceed. A duplicate download is a much
            # smaller problem than a lane that will not sync.
            self.held = True
        return self

    def __exit__(self, *exc):
        if self.held:
            try:
                os.remove(LOCK_PATH)
            except Exception:
                pass
        return False


def sync(state, drive_service=None):
    """Wrapper holding the lock. The real work is in _sync."""
    with _Lock() as lock:
        if not lock.held:
            log("another sync is already running — skipping this one")
            return 0, 0
        return _sync(state, drive_service)


def _sync(state, drive_service=None):
    """Download any Drive video not already pulled. Returns (new, skipped).

    Never raises: a Drive outage must not stop videos already in the pool from
    being published. But it is LOUD, because silence here looks identical to
    "nothing new to post".
    """
    pulled = state.setdefault("drive", {})

    try:
        if drive_service is None:
            from google_services import get_drive_service
            drive_service = get_drive_service()
    except Exception as e:
        log(f"ERROR: could not authenticate to Drive ({type(e).__name__}: "
            f"{str(e)[:140]})")
        log(f"    {REAUTH_HINT}")
        return 0, 0

    try:
        files = list_videos(drive_service)
    except Exception as e:
        log(f"ERROR: could not list {FOLDER_URL} ({type(e).__name__}: "
            f"{str(e)[:140]})")
        log(f"    {REAUTH_HINT}")
        return 0, 0

    os.makedirs(reel_config.DROP_DIR, exist_ok=True)

    new = skipped = renamed = 0
    for f in files:
        fid = f["id"]
        rec = pulled.get(fid)

        # ALWAYS refresh the stored title, download or not. The filename is how
        # a product gets declared, so a rename in Drive has to reach the lane.
        if rec and rec.get("name") != f["name"]:
            log(f"  renamed in Drive: {rec.get('name')} -> {f['name']}")
            rec["name"] = f["name"]
            renamed += 1

        if rec and os.path.exists(os.path.join(reel_config.DROP_DIR,
                                               rec["local"])):
            skipped += 1
            continue
        # Already pulled once but the local copy is gone: Marcus deleted it
        # from the pool on purpose. Do NOT silently re-download it.
        if rec and rec.get("downloaded"):
            skipped += 1
            continue

        name = safe_name(f["name"])
        if not name.lower().endswith(reel_config.VIDEO_EXTS):
            name += ".mp4"
        dest = os.path.join(reel_config.DROP_DIR, name)

        # Never clobber a different file that happens to share a name.
        stem, ext = os.path.splitext(name)
        n = 2
        while os.path.exists(dest) and not (
                rec and rec.get("local") == os.path.basename(dest)):
            name = f"{stem}_{n}{ext}"
            dest = os.path.join(reel_config.DROP_DIR, name)
            n += 1

        size = int(f.get("size") or 0)
        if size and size > reel_config.MAX_SOURCE_BYTES:
            # Say this ONCE. This runs every 15 minutes; a permanently
            # oversized file would otherwise repeat the same line forever and
            # bury anything that actually matters.
            if not rec:
                log(f"  SKIP {f['name']}: {size / 1024 / 1024:.0f} MB is over "
                    f"the {reel_config.MAX_SOURCE_BYTES // 1024 // 1024} MB "
                    f"download cap")
            pulled[fid] = {"local": name, "downloaded": False,
                           "skipped": "too large", "name": f["name"],
                           "rel_path": f.get("rel_path", "")}
            skipped += 1
            continue

        try:
            from google_services import download_file_from_drive
            where = f.get("rel_path", "")
            log(f"  downloading {('[' + where + '] ') if where else ''}"
                f"{f['name']}"
                + (f" ({size / 1024 / 1024:.1f} MB)" if size else ""))
            data = download_file_from_drive(drive_service, fid)
            tmp = dest + ".part"
            with open(tmp, "wb") as fh:
                fh.write(data)
            os.replace(tmp, dest)          # atomic: never a half file in the pool
            pulled[fid] = {"local": name, "downloaded": True,
                           "name": f["name"],
                           "rel_path": f.get("rel_path", ""),
                           "modifiedTime": f.get("modifiedTime", "")}
            new += 1
            log(f"  -> {name}")
        except Exception as e:
            log(f"  ERROR downloading {f['name']}: {type(e).__name__}: "
                f"{str(e)[:140]}")

    # QUIET WHEN NOTHING CHANGED. A tick fires every 15 minutes and almost
    # always has nothing to do; logging on every one buries the ticks that
    # matter and makes a real Drive failure harder to spot, not easier.
    if new or renamed:
        log(f"{len(files)} video(s) in Drive; {new} new, {renamed} renamed")
    return new, skipped


if __name__ == "__main__":
    import reel_runner
    st = reel_runner.load_state()
    n, s = sync(st)
    reel_runner.save_state(st)
    print(f"\n{n} new, {s} already pulled.\n{FOLDER_URL}\n")
