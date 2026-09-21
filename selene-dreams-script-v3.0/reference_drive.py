"""
reference_drive.py — Marcus's reference images, from Drive to every writer
=============================================================================
VERSION 1.1 — 2026-09-16

WHAT THIS IS
    "02. Reference Images" in Drive (config.DRIVE_REFERENCE_IMAGES_FOLDER_ID)
    was v2.0's per-month lookup folder and has been read by NOTHING since the
    2026-07-22 column cleanup. Marcus asked to refit it as the one place he
    and the team dump images they like, for the image lane AND the
    educational lane. Until now the only reference input was a LOCAL folder
    on the Mac (config.REFERENCE_IMAGES_DIR, wired 2026-08-26) that only he
    could reach and only prompt_runner read.

    Drive layout (created 2026-09-16):
      01. Style        -> lane "style":        prompt writer + Monday screener
      02. Educational  -> lane "educational":  carousel picture editor
      00. Archive      -> IGNORED (the old 2026/month folders were moved here)
      top-level files  -> style

    SETS (1.1): any sub-folder INSIDE a lane folder is one reference POST —
    e.g. "02. Educational / brooklinen - thread count myth / 01.png, 02.png".
    Marcus screenshots competitor carousels slide by slide; without sets each
    slide was an unrelated single, one 7-slide post filled the whole
    "newest 6" window, and the vision note described slide 4 without knowing
    slide 1 existed. A set is:
      - downloaded to <lane>/<folder name>/<slide files>
      - described in ONE vision call as a carousel (hook -> structure ->
        payoff), reading the slides in filename order
      - counted as ONE reference toward MAX_VIEW, with all its slides listed
      - framed to the writers as "borrow the structure and pacing, never the
        brand, layout, colours or copy" — these are mostly competitor posts
      - optionally annotated by a notes.txt / notes.md in the same folder:
        Marcus's own one-liner on WHY he saved it. Highest-signal input there
        is, so it goes to the describer and into the prompt block verbatim.
    Loose files directly in a lane folder stay singles, exactly as in 1.0.

STYLE ONLY, BY DECISION
    Marcus chose "Style only" on 2026-09-16: these images are VIEWED by the
    writers for mood, composition, light and styling. They are never passed
    to the image generator as pixels. Several are competitor photos; feeding
    those into a multi-reference generator can land near-identical to the
    original, and the 2026-09-14 flow diagnostic already flagged AI imagery
    of named products as a risk. Nothing in this module hands a file to
    replicate_service, and nothing should.

THE DESIGN, SAME SHAPE AS reel_drive
    Drive is the source; the local folder is a CACHE the consumers read.
    sync() downloads anything new by Drive file id into
        <REFERENCE_IMAGES_DIR>/style/  or  /educational/  (or a set folder)
    and records it in _manifest.json. A file removed from Drive is removed
    locally on the next sync — Drive is where he withdraws a reference.
    Fail-open: a dead token or a Drive outage leaves the cache as it was and
    the consumers keep reading it. LOUD about the token, because a quiet
    Drive failure here means "I dropped images in and nothing changed".

WORDS FOR THE WRITERS THAT CANNOT SEE
    Each new image (or set) gets ONE vision call (describe_new): what it
    shows, why it is on-brand, what to borrow. The notes go into the manifest
    and into _notes-<lane>.md, so text-only consumers (the educational
    picture editor judges descriptions, not pixels) still get his taste.
    Bounded per run.

MANIFEST SHAPE (1.1)
    files: { <drive file id>: {name, local, lane, downloaded, note?, set?} }
             "set" = the Drive folder id of the set the file belongs to
    sets:  { <drive folder id>: {name, lane, local_dir, files:[ids in slide
             order], marcus_note, note?, note_version?, added_at} }
    1.0 manifests load unchanged (no "sets" key -> empty).

CHANGELOG
    1.1  2026-09-16  SETS: a sub-folder inside a lane folder is one reference
                     post — slides in filename order, one carousel vision call
                     (prompts/reference-set.md v1), one slot in MAX_VIEW,
                     competitor framing in the prompt block, notes.txt
                     support. Files moved in/out of a set in Drive move
                     locally. _lane_items() is the new unit; _lane_files()
                     kept for callers that want flat paths. CLI lists sets.
                     Newest-first now uses Drive modifiedTime, not local
                     download time (a 25-file batch sorted arbitrarily).
    1.0  2026-09-16  First build.
=============================================================================
"""

import json
import os
import re
import time

import config

VERSION = "1.1"

FOLDER_ID = config.DRIVE_REFERENCE_IMAGES_FOLDER_ID
FOLDER_URL = f"https://drive.google.com/drive/folders/{FOLDER_ID}"
ROOT = config.REFERENCE_IMAGES_DIR
MANIFEST = os.path.join(ROOT, "_manifest.json")
LOCK_PATH = os.path.join(ROOT, "_sync.lock")
LOCK_STALE_SECONDS = 15 * 60

LANES = ("style", "educational")
LANE_FOLDERS = {"01. style": "style", "02. educational": "educational"}
IGNORED_PREFIXES = ("00.", "_", ".")          # 00. Archive and hidden things
IGNORED_NAMES = ("archive",)
IMAGE_MIMES = ("image/jpeg", "image/png", "image/webp")
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
SKIPPED_EXTS = (".heic", ".heif")              # Claude cannot view these
NOTE_FILENAMES = ("notes.txt", "notes.md", "note.txt", "note.md")
NOTE_MAX_CHARS = 600
MAX_FOLDER_DEPTH = 3
MAX_BYTES = 25 * 1024 * 1024

MAX_VIEW = getattr(config, "REFERENCE_MAX_VIEW", 6)          # per prompt
MAX_DESCRIBE_PER_RUN = getattr(config, "REFERENCE_MAX_DESCRIBE_PER_RUN", 8)

REAUTH_HINT = (
    "The Drive OAuth token is dead or missing. Fix it with:\n"
    "      cd <v3.0 folder> && python3 reauth_drive.py")


def log(msg):
    print(f"[reference_drive] {msg}", flush=True)


def safe_name(name):
    name = os.path.basename(name).strip()
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name)
    return name or "reference.jpg"


def _natural_key(s):
    """'02.png' < '10.png', 'IMG_9.jpg' < 'IMG_10.jpg'."""
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", os.path.basename(s or ""))]


# ── manifest ────────────────────────────────────────────────────────────────

def load_manifest():
    try:
        with open(MANIFEST) as f:
            m = json.load(f)
        m.setdefault("files", {})
        m.setdefault("sets", {})
        return m
    except Exception:
        return {"version": VERSION, "files": {}, "sets": {}, "synced_at": ""}


def save_manifest(m):
    os.makedirs(ROOT, exist_ok=True)
    m["version"] = VERSION
    tmp = MANIFEST + ".tmp"
    with open(tmp, "w") as f:
        json.dump(m, f, indent=2)
    os.replace(tmp, MANIFEST)


def lane_dir(lane):
    return os.path.join(ROOT, lane)


# ── Drive listing ───────────────────────────────────────────────────────────

def _ignored(name):
    n = name.strip().lower()
    return n.startswith(IGNORED_PREFIXES) or n in IGNORED_NAMES


def _children(drive, parent_id, folders, notes=False):
    if folders:
        q = (f"'{parent_id}' in parents and trashed = false and "
             f"mimeType = 'application/vnd.google-apps.folder'")
        fields = "nextPageToken, files(id, name)"
    elif notes:
        q = (f"'{parent_id}' in parents and trashed = false and ("
             f"mimeType = 'text/plain' or mimeType = 'text/markdown' or "
             f"mimeType = 'application/vnd.google-apps.document')")
        fields = "nextPageToken, files(id, name, mimeType, size)"
    else:
        q = (f"'{parent_id}' in parents and trashed = false and ("
             + " or ".join(f"mimeType = '{m}'" for m in IMAGE_MIMES)
             + " or mimeType = 'image/heic' or mimeType = 'image/heif')")
        fields = "nextPageToken, files(id, name, mimeType, size, modifiedTime)"
    out, token = [], None
    while True:
        resp = drive.files().list(
            q=q, spaces="drive", fields=fields, pageToken=token,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
            pageSize=200).execute()
        out.extend(resp.get("files", []))
        token = resp.get("nextPageToken")
        if not token:
            return out


def _read_set_note(drive, folder_id):
    """notes.txt / notes.md inside a set folder -> Marcus's one-liner.
    '' when absent or unreadable. Google Docs are exported as plain text."""
    try:
        for f in _children(drive, folder_id, folders=False, notes=True):
            if f.get("name", "").strip().lower() not in NOTE_FILENAMES:
                continue
            if f.get("mimeType") == "application/vnd.google-apps.document":
                data = drive.files().export(
                    fileId=f["id"], mimeType="text/plain").execute()
            else:
                from google_services import download_file_from_drive
                data = download_file_from_drive(drive, f["id"])
            text = (data.decode("utf-8", "replace") if isinstance(data, bytes)
                    else str(data)).strip()
            return " ".join(text.split())[:NOTE_MAX_CHARS]
    except Exception as e:
        log(f"  could not read the set note ({type(e).__name__})")
    return ""


def list_images(drive, folder_id=None, lane="style", _depth=0,
                set_info=None, sets=None):
    """Every image under the folder, each tagged with its lane and — when it
    lives in a sub-folder of a lane folder — its set. `sets` (dict, filled in
    place) collects {folder id: {name, lane, marcus_note}}.
    00. Archive (and anything starting 00./_/.) is never entered."""
    folder_id = folder_id or FOLDER_ID
    if sets is None:
        sets = {}
    files = _children(drive, folder_id, folders=False)
    for f in files:
        f["lane"] = lane
        if set_info:
            f["set"] = set_info["id"]
    if _depth >= MAX_FOLDER_DEPTH:
        return files
    for sub in _children(drive, folder_id, folders=True):
        if _ignored(sub["name"]):
            continue
        key = sub["name"].strip().lower()
        if key in LANE_FOLDERS:
            sub_lane, sub_set = LANE_FOLDERS[key], None
        elif set_info is None and _depth >= 1:
            # a folder inside a lane folder (or inside a nested folder of
            # the root) = one reference post
            sub_lane = lane
            sub_set = {"id": sub["id"], "name": sub["name"].strip(), "lane": lane,
                       "marcus_note": _read_set_note(drive, sub["id"])}
            sets[sub["id"]] = sub_set
        else:
            sub_lane, sub_set = lane, set_info     # deeper folders join the set
        files.extend(list_images(drive, sub["id"], sub_lane, _depth + 1,
                                 sub_set, sets))
    return files


# ── lock ────────────────────────────────────────────────────────────────────

class _Lock:
    def __init__(self):
        self.held = False

    def __enter__(self):
        try:
            os.makedirs(ROOT, exist_ok=True)
            if os.path.exists(LOCK_PATH):
                if time.time() - os.path.getmtime(LOCK_PATH) < LOCK_STALE_SECONDS:
                    return self
            with open(LOCK_PATH, "w") as f:
                f.write(str(os.getpid()))
            self.held = True
        except Exception:
            self.held = True
        return self

    def __exit__(self, *exc):
        if self.held:
            try:
                os.remove(LOCK_PATH)
            except Exception:
                pass
        return False


# ── sync ────────────────────────────────────────────────────────────────────

def _migrate_legacy(m):
    """One-off: the 11 photos Marcus put in the flat local folder on 2026-08-26
    become style references, keyed as local-only so a Drive sync never
    removes them."""
    if m.get("legacy_migrated"):
        return 0
    moved = 0
    try:
        os.makedirs(lane_dir("style"), exist_ok=True)
        for f in sorted(os.listdir(ROOT)):
            src = os.path.join(ROOT, f)
            if not os.path.isfile(src) or not f.lower().endswith(IMAGE_EXTS):
                continue
            dest = os.path.join(lane_dir("style"), f)
            if os.path.exists(dest):
                continue
            os.replace(src, dest)
            m["files"][f"local:{f}"] = {
                "name": f, "local": os.path.join("style", f), "lane": "style",
                "source": "local", "downloaded": True,
                "added_at": time.strftime("%Y-%m-%dT%H:%M")}
            moved += 1
        m["legacy_migrated"] = True
        if moved:
            log(f"moved {moved} legacy local reference(s) into style/")
    except Exception as e:
        log(f"legacy migration skipped ({type(e).__name__})")
    return moved


def _target_dir(lane, set_rec):
    """Where a file belongs locally: <lane>/ or <lane>/<set folder>/."""
    if set_rec:
        return os.path.join(lane_dir(lane), safe_name(set_rec["name"]))
    return lane_dir(lane)


def sync(drive=None):
    """Pull new reference images down; drop ones removed from Drive.
    Returns (new, removed). Never raises."""
    with _Lock() as lock:
        if not lock.held:
            log("another sync is running — skipping")
            return 0, 0
        return _sync(drive)


def _sync(drive=None):
    m = load_manifest()
    files_rec = m["files"]
    sets_rec = m["sets"]
    _migrate_legacy(m)

    try:
        if drive is None:
            from google_services import get_drive_service
            drive = get_drive_service()
        remote_sets = {}
        remote = list_images(drive, sets=remote_sets)
    except Exception as e:
        log(f"ERROR: cannot reach {FOLDER_URL} ({type(e).__name__}: "
            f"{str(e)[:120]}) — using the cached references")
        log(f"    {REAUTH_HINT}")
        save_manifest(m)
        return 0, 0

    # Sets first, so every file below can find its folder.
    for sid, s in remote_sets.items():
        rec = sets_rec.get(sid)
        if not rec:
            sets_rec[sid] = {
                "name": s["name"], "lane": s["lane"], "files": [],
                "marcus_note": s.get("marcus_note", ""),
                "local_dir": os.path.relpath(_target_dir(s["lane"], s), ROOT),
                "added_at": time.strftime("%Y-%m-%dT%H:%M")}
            log(f"  new set: {s['name']} ({s['lane']})")
        else:
            if rec.get("name") != s["name"] or rec.get("lane") != s["lane"]:
                rec["name"], rec["lane"] = s["name"], s["lane"]
                rec["local_dir"] = os.path.relpath(_target_dir(s["lane"], s), ROOT)
            if s.get("marcus_note") != rec.get("marcus_note", ""):
                rec["marcus_note"] = s.get("marcus_note", "")
                rec.pop("note", None)          # his words changed: re-describe
        sets_rec[sid]["files"] = []            # rebuilt from the listing below

    new = removed = 0
    seen = set()
    for f in remote:
        fid, name, lane = f["id"], f["name"], f.get("lane", "style")
        sid = f.get("set")
        set_rec = sets_rec.get(sid) if sid else None
        seen.add(fid)
        rec = files_rec.get(fid)
        low = name.lower()
        if low.endswith(SKIPPED_EXTS) or f.get("mimeType") in ("image/heic", "image/heif"):
            if not rec:
                log(f"  SKIP {name}: HEIC cannot be viewed — export it as JPG")
                files_rec[fid] = {"name": name, "lane": lane, "downloaded": False,
                                  "skipped": "heic"}
            continue
        size = int(f.get("size") or 0)
        if size > MAX_BYTES:
            if not rec:
                log(f"  SKIP {name}: {size // 1024 // 1024} MB is over the cap")
                files_rec[fid] = {"name": name, "lane": lane, "downloaded": False,
                                  "skipped": "too large"}
            continue

        target_dir = _target_dir(lane, set_rec)

        # Moved in Drive (between lanes, or in/out of a set) -> move locally.
        if rec and rec.get("downloaded") and rec.get("local"):
            old = os.path.join(ROOT, rec["local"])
            if os.path.normpath(os.path.dirname(old)) != os.path.normpath(target_dir):
                newp = os.path.join(target_dir, os.path.basename(rec["local"]))
                try:
                    os.makedirs(target_dir, exist_ok=True)
                    if os.path.exists(old):
                        os.replace(old, newp)
                    rec["lane"], rec["local"] = lane, os.path.relpath(newp, ROOT)
                    if sid:
                        rec["set"] = sid
                    else:
                        rec.pop("set", None)
                    rec.pop("note", None)      # context changed
                    log(f"  {name}: now in {os.path.relpath(target_dir, ROOT)}/")
                except Exception as e:
                    log(f"  could not move {name} ({type(e).__name__})")
        if rec and rec.get("downloaded") and os.path.exists(
                os.path.join(ROOT, rec.get("local", ""))):
            if rec.get("name") != name:
                rec["name"] = name
            if set_rec is not None:
                set_rec["files"].append(fid)
            continue

        local = safe_name(name)
        if not local.lower().endswith(IMAGE_EXTS):
            local += ".jpg"
        os.makedirs(target_dir, exist_ok=True)
        dest = os.path.join(target_dir, local)
        stem, ext = os.path.splitext(local)
        n = 2
        while os.path.exists(dest):
            local = f"{stem}_{n}{ext}"
            dest = os.path.join(target_dir, local)
            n += 1
        try:
            from google_services import download_file_from_drive
            data = download_file_from_drive(drive, fid)
            with open(dest, "wb") as fh:
                fh.write(data)
            files_rec[fid] = {
                "name": name, "local": os.path.relpath(dest, ROOT), "lane": lane,
                "source": "drive", "downloaded": True,
                "modified": f.get("modifiedTime", ""),
                "added_at": time.strftime("%Y-%m-%dT%H:%M")}
            if sid:
                files_rec[fid]["set"] = sid
                set_rec["files"].append(fid)
                set_rec.pop("note", None)      # a new slide: re-describe
            new += 1
            log(f"  pulled {name} -> {os.path.relpath(target_dir, ROOT)}/")
        except Exception as e:
            log(f"  could not download {name} ({type(e).__name__}: "
                f"{str(e)[:100]})")

    # Withdrawn in Drive -> gone locally. Local-only legacy files are kept.
    for fid in [k for k, v in files_rec.items()
                if v.get("source") == "drive" and k not in seen]:
        rec = files_rec.pop(fid)
        p = os.path.join(ROOT, rec.get("local") or "")
        try:
            if rec.get("local") and os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
        if rec.get("set") in sets_rec:
            sets_rec[rec["set"]].pop("note", None)   # a slide left: re-describe
        removed += 1
        log(f"  removed from Drive, dropped: {rec.get('name')}")

    # Sets: slide order by filename; sets gone from Drive are dropped.
    for sid in list(sets_rec):
        s = sets_rec[sid]
        if sid not in remote_sets:
            sets_rec.pop(sid)
            for v in files_rec.values():
                if v.get("set") == sid:
                    v.pop("set", None)
            d = os.path.join(ROOT, s.get("local_dir") or "")
            try:
                if s.get("local_dir") and os.path.isdir(d) and not os.listdir(d):
                    os.rmdir(d)
            except Exception:
                pass
            log(f"  set removed from Drive, dropped: {s.get('name')}")
            continue
        s["files"].sort(key=lambda fid: _natural_key(files_rec.get(fid, {}).get("local", "")))

    m["synced_at"] = time.strftime("%Y-%m-%dT%H:%M")
    save_manifest(m)
    if new or removed:
        _write_notes(m)
    return new, removed


# ── vision notes ────────────────────────────────────────────────────────────

NOTE_SCHEMA = {
    "shows":    {"type": "str"},
    "on_brand": {"type": "str"},
    "borrow":   {"type": "str"},
}

SET_NOTE_SCHEMA = {
    "shows":     {"type": "str"},
    "structure": {"type": "str"},
    "on_brand":  {"type": "str"},
    "borrow":    {"type": "str"},
}


def _set_paths(m, s):
    out = []
    for fid in s.get("files", []):
        v = m["files"].get(fid) or {}
        if v.get("downloaded") and v.get("local"):
            p = os.path.join(ROOT, v["local"])
            if os.path.exists(p):
                out.append(p)
    return out


def describe_new(limit=None):
    """One vision call per new image or set -> note in the manifest.
    Bounded. Never raises; a failed call is retried on a later run."""
    limit = MAX_DESCRIBE_PER_RUN if limit is None else limit
    m = load_manifest()
    todo_sets = [(k, v) for k, v in m["sets"].items()
                 if not v.get("note") and _set_paths(m, v)]
    todo_files = [(k, v) for k, v in m["files"].items()
                  if v.get("downloaded") and not v.get("note") and not v.get("set")]
    todo = ([("set", k, v) for k, v in todo_sets]
            + [("file", k, v) for k, v in todo_files])[:limit]
    if not todo:
        return 0
    try:
        import tempfile
        from claude_client import invoke_claude_json, load_prompt
        template, version = load_prompt("reference-note")
        try:
            set_template, set_version = load_prompt("reference-set")
        except Exception:
            set_template, set_version = None, None
    except Exception as e:
        log(f"cannot describe references ({type(e).__name__}) — the writers "
            f"still get the images themselves")
        return 0
    done = 0
    for kind, key, rec in todo:
        workdir = tempfile.mkdtemp(prefix="selene_refnote_")
        out_path = os.path.join(workdir, "note.json")
        if kind == "set":
            if not set_template:
                log("  prompts/reference-set.md missing — sets stay undescribed")
                continue
            paths = _set_paths(m, rec)
            prompt = set_template.format(
                lane=rec.get("lane", "educational"), set_name=rec.get("name", ""),
                slide_count=len(paths),
                slide_list="\n".join(f"  {i}. {p}" for i, p in enumerate(paths, 1)),
                marcus_note=(rec.get("marcus_note") or "(none given)"),
                out_path=out_path)
            schema, keys, ver = SET_NOTE_SCHEMA, ("shows", "structure", "on_brand", "borrow"), set_version
            label = f"set {rec.get('name')} ({len(paths)} slides)"
        else:
            path = os.path.join(ROOT, rec["local"])
            if not os.path.exists(path):
                continue
            prompt = template.format(image_path=path, lane=rec.get("lane", "style"),
                                     out_path=out_path)
            schema, keys, ver = NOTE_SCHEMA, ("shows", "on_brand", "borrow"), version
            label = rec["name"]
        try:
            ok, result = invoke_claude_json(
                prompt, workdir, out_path, schema=schema,
                stage="reference", timeout=300 if kind == "set" else 240)
        except Exception as e:
            ok, result = False, str(e)
        if ok:
            rec["note"] = {k: str(result.get(k, "")).strip() for k in keys}
            rec["note_version"] = ver
            done += 1
            log(f"  described {label}")
        else:
            log(f"  could not describe {label} ({str(result)[:80]})")
    if done:
        save_manifest(m)
        _write_notes(m)
    return done


def _lane_items(m, lane):
    """The unit the writers see: singles and sets, newest first.
    Each item: {kind, name, paths, note, marcus_note, mtime, rec}."""
    out = []
    for v in m["files"].values():
        if v.get("set") or not (v.get("downloaded") and v.get("lane") == lane and v.get("local")):
            continue
        p = os.path.join(ROOT, v["local"])
        if os.path.exists(p):
            out.append({"kind": "single", "name": v.get("name", ""), "paths": [p],
                        "note": v.get("note") or {}, "marcus_note": "",
                        "mtime": _recency(v, p), "rec": v})
    for s in m.get("sets", {}).values():
        if s.get("lane") != lane:
            continue
        paths = _set_paths(m, s)
        if not paths:
            continue
        out.append({"kind": "set", "name": s.get("name", ""), "paths": paths,
                    "note": s.get("note") or {}, "marcus_note": s.get("marcus_note", ""),
                    "mtime": max(_recency(m["files"].get(f, {}), p)
                                 for f, p in zip(s.get("files", []), paths)), "rec": s})
    out.sort(key=lambda it: it["mtime"], reverse=True)
    return out


def _recency(rec, path):
    """Newest-first key. Drive's modifiedTime (when Marcus dropped it in)
    beats the local mtime, which is just when THIS Mac downloaded it — a
    batch of 25 pulled in one sync would otherwise sort arbitrarily."""
    for k in ("modified", "added_at"):
        t = rec.get(k) or ""
        if t:
            try:
                from datetime import datetime, timezone
                t = t.replace("Z", "+00:00")
                d = datetime.fromisoformat(t)
                if d.tzinfo is None:
                    d = d.replace(tzinfo=timezone.utc)
                return d.timestamp()
            except Exception:
                pass
    try:
        return os.path.getmtime(path)
    except Exception:
        return 0.0


def _lane_files(m, lane):
    """Flat (path, file record) list, newest first — the 1.0 shape, for
    callers that want individual files. Set slides are included."""
    out = []
    for v in m["files"].values():
        if v.get("downloaded") and v.get("lane") == lane and v.get("local"):
            p = os.path.join(ROOT, v["local"])
            if os.path.exists(p):
                out.append((p, v))
    out.sort(key=lambda t: os.path.getmtime(t[0]), reverse=True)
    return out


def _item_line(it, with_paths=True):
    note = it["note"]
    if it["kind"] == "set":
        head = (f"SET \"{it['name']}\" — one reference post, {len(it['paths'])} "
                f"slide(s), read IN ORDER")
        bits = []
        if it["marcus_note"]:
            bits.append(f"Marcus: \"{it['marcus_note']}\"")
        if note.get("shows"):
            bits.append(note["shows"])
        if note.get("structure"):
            bits.append(f"Structure: {note['structure']}")
        line = head + (" — " + " ".join(bits) if bits else "")
        if with_paths:
            line += "\n" + "\n".join(f"      {i}. {p}" for i, p in enumerate(it["paths"], 1))
        return line
    tail = f" — {note['shows']}" if note.get("shows") else ""
    return (it["paths"][0] if with_paths else it["name"]) + tail


def _write_notes(m):
    """_notes-<lane>.md: the words version of the folder, for humans and for
    writers that only read text."""
    for lane in LANES:
        try:
            lines = [f"# Reference notes — {lane}",
                     f"Generated by reference_drive.py {VERSION}; do not edit. "
                     f"Add or remove images in Drive: {FOLDER_URL}", ""]
            for it in _lane_items(m, lane):
                note = it["note"]
                if it["kind"] == "set":
                    lines.append(f"- SET {it['name']} ({len(it['paths'])} slides)"
                                 + (f" — Marcus: {it['marcus_note']}" if it["marcus_note"] else ""))
                    if note:
                        lines.append(f"    Shows: {note.get('shows', '')} "
                                     f"Structure: {note.get('structure', '')} "
                                     f"On-brand because: {note.get('on_brand', '')} "
                                     f"Borrow: {note.get('borrow', '')}")
                    else:
                        lines.append("    (not yet described)")
                elif note:
                    lines.append(f"- {it['name']}: {note.get('shows', '')} "
                                 f"On-brand because: {note.get('on_brand', '')} "
                                 f"Borrow: {note.get('borrow', '')}")
                else:
                    lines.append(f"- {it['name']}: (not yet described)")
            with open(os.path.join(ROOT, f"_notes-{lane}.md"), "w") as fh:
                fh.write("\n".join(lines) + "\n")
        except Exception as e:
            log(f"could not write notes for {lane} ({type(e).__name__})")


# ── what consumers call ─────────────────────────────────────────────────────

def items(lane, limit=None):
    """Newest reference items (singles and sets) for a lane. Never raises."""
    try:
        limit = MAX_VIEW if limit is None else limit
        return _lane_items(load_manifest(), lane)[:limit]
    except Exception:
        return []


def files(lane, limit=None):
    """Newest local reference paths for a lane, flattened — a set contributes
    all its slides but counts once toward the limit. Never raises."""
    try:
        limit = MAX_VIEW if limit is None else limit
        out = []
        for it in _lane_items(load_manifest(), lane)[:limit]:
            out.extend(it["paths"])
        return out
    except Exception:
        return []


def notes_text(lane, limit=None):
    """The described references as plain text, newest first. '' if none."""
    try:
        limit = MAX_VIEW * 2 if limit is None else limit
        rows = []
        for it in _lane_items(load_manifest(), lane)[:limit]:
            note = it["note"]
            if not note:
                continue
            if it["kind"] == "set":
                rows.append(f"  - SET {it['name']}: {note.get('shows', '')} "
                            f"Structure: {note.get('structure', '')} "
                            f"Borrow: {note.get('borrow', '')}")
            else:
                rows.append(f"  - {it['name']}: {note.get('shows', '')} "
                            f"Borrow: {note.get('borrow', '')}")
        return "\n".join(rows)
    except Exception:
        return ""


def section(lane, limit=None, heading=None):
    """Prompt block: view these files, plus their notes. '' when empty, so a
    template placeholder simply vanishes. A set is one entry with all its
    slides listed and counts once toward the limit."""
    try:
        m = load_manifest()
        rows = _lane_items(m, lane)
        if not rows:
            return ""
        limit = MAX_VIEW if limit is None else limit
        shown = rows[:limit]
        suffix = (f" (newest {len(shown)} of {len(rows)})"
                  if len(rows) > len(shown) else "")
        heading = heading or "MARCUS'S OWN REFERENCE IMAGES"
        lines = [f"  - {_item_line(it)}" for it in shown]
        has_sets = any(it["kind"] == "set" for it in shown)
        set_rule = (
            " A SET is one whole post (usually a competitor's carousel) "
            "saved slide by slide: read its slides in the numbered order and "
            "take the STRUCTURE — how it hooks, how it sequences the teaching, "
            "where the payoff lands, how much it says per slide. Never its "
            "brand, layout, colours, typography or copy. Where Marcus left a "
            "note on a set, that note is the reason it is here — weight it "
            "above the description." if has_sets else "")
        return (
            f"{heading}{suffix} — view EVERY file below with the Read tool "
            f"before you write. These are hand-picked by Marcus and his team "
            f"in Drive as examples of what they want: use them for mood, "
            f"composition, light and styling. Precedence: brand-guide.md "
            f"rules still win; these outrank scraped references on taste. "
            f"Never copy one literally, and never reproduce a competitor's "
            f"product — borrow the feel.{set_rule}\n" + "\n".join(lines) + "\n")
    except Exception as e:
        log(f"section unavailable ({type(e).__name__})")
        return ""


def refresh(describe=True):
    """sync + describe, both fail-open. What every consumer calls first."""
    try:
        new, removed = sync()
    except Exception as e:
        log(f"sync failed ({type(e).__name__})")
        new = removed = 0
    if describe:
        try:
            describe_new()
        except Exception as e:
            log(f"describe failed ({type(e).__name__})")
    return new, removed


if __name__ == "__main__":
    import sys
    if "--sync" in sys.argv or "--refresh" in sys.argv:
        n, r = refresh(describe="--no-describe" not in sys.argv)
        print(f"{n} new, {r} removed")
    if "--describe" in sys.argv:
        print(f"{describe_new()} described")
    m = load_manifest()
    print(f"\nReference images — {FOLDER_URL}\nlast sync: {m.get('synced_at') or 'never'}")
    for lane in LANES:
        rows = _lane_items(m, lane)
        n_sets = sum(1 for it in rows if it["kind"] == "set")
        print(f"\n{lane}: {len(rows)} item(s) ({n_sets} set(s)), "
              f"{sum(1 for it in rows if it['note'])} described")
        for it in rows[:MAX_VIEW]:
            if it["kind"] == "set":
                print(f"  SET {it['name']} [{len(it['paths'])} slides]"
                      + (f" — {it['note']['shows'][:70]}" if it["note"] else ""))
            else:
                print(f"  {os.path.basename(it['paths'][0])}"
                      + (f" — {it['note']['shows'][:70]}" if it["note"] else ""))
    print()
