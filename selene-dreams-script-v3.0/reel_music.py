"""
reel_music.py — give a silent reel something to listen to
=============================================================================
VERSION 1.1 — 2026-09-11

WHY
    The first live trial reel published with no sound. Not an API limit and not
    a pipeline bug: the DJI source carried an audio stream containing digital
    silence (-91 dBFS peak). Silent reels are a real disadvantage — audio drives
    watch-through, and watch-through is the only thing that drives trial reel
    distribution.

    Instagram-library music cannot be attached through the API at all
    (selene-ig-api-limits). The only automatable route is baking an owned or
    licensed track into the file before upload, which is cheap here because
    video_host already re-encodes every clip for delivery.

OFF BY DEFAULT, IN THE MOST LITERAL SENSE
    There is no flag to set. The Drive folder "05. Video Reel /
    02. Audio Content" starts empty, and
    an empty folder means reels publish silent exactly as they do today. Drop a
    track in and the lane starts using it on the next tick. Marcus said he had
    no preference, so this costs him nothing until he decides.

TWO RULES THAT ARE NOT NEGOTIABLE
    1. NEVER overwrite real audio. Music is added only when the video has
       nothing audible (video_host.is_effectively_silent). If he shot location
       sound, that sound survives.
    2. ONLY licensed or owned audio belongs in that folder. Artlist is the
       source already connected for this brand. Ripping Instagram-library music
       into a file is a rights problem, not a technical one, and this module
       cannot tell the difference — so the folder's contents are his warranty.

CHANGELOG
    1.1  2026-09-11  THE CONTROL TAB NOW ACTUALLY CONTROLS MUSIC. maybe_add
                     re-ran its own silence test and overrode the caller, so
                     "Audio in video? = no" in the Videos tab was silently
                     ignored on any clip that had SOME audio — wind on drone
                     footage, room tone, a stray bump. The sheet said
                     "-> Music: yes", the log said "leaving it alone", and the
                     reel published with the noise. Two components deciding the
                     same question independently, which is the bug, not the
                     threshold. reel_runner now owns the decision and passes it
                     in; this module executes it.
    1.0  2026-09-09  First build.
=============================================================================
"""

import os
import subprocess

import reel_config

AUDIO_MIMES = ("audio/mpeg", "audio/mp4", "audio/x-m4a", "audio/aac",
               "audio/wav", "audio/x-wav", "audio/flac", "audio/ogg")


def log(msg):
    print(f"[reel_music] {msg}", flush=True)


# ── getting tracks off Drive ────────────────────────────────────────────────

def sync(state, drive_service=None):
    """Mirror the Drive music folder locally. Returns the count available.

    Fail-open and quiet, like reel_drive: no music must never stop a publish.
    """
    pulled = state.setdefault("music", {})
    try:
        if drive_service is None:
            from google_services import get_drive_service
            drive_service = get_drive_service()
        q = (f"'{reel_config.MUSIC_FOLDER_ID}' in parents and trashed = false")
        resp = drive_service.files().list(
            q=q, spaces="drive", fields="files(id, name, mimeType, size)",
            supportsAllDrives=True, includeItemsFromAllDrives=True,
            pageSize=200).execute()
        files = [f for f in resp.get("files", [])
                 if f.get("mimeType") in AUDIO_MIMES
                 or f["name"].lower().endswith(reel_config.MUSIC_EXTS)]
    except Exception as e:
        log(f"could not read the music folder ({type(e).__name__}) — "
            f"continuing without music")
        return len(available())

    os.makedirs(reel_config.MUSIC_DIR, exist_ok=True)
    new = 0
    for f in files:
        rec = pulled.get(f["id"])
        local = os.path.join(reel_config.MUSIC_DIR, _safe(f["name"]))
        if rec and os.path.exists(local):
            continue
        try:
            from google_services import download_file_from_drive
            data = download_file_from_drive(drive_service, f["id"])
            tmp = local + ".part"
            with open(tmp, "wb") as fh:
                fh.write(data)
            os.replace(tmp, local)
            pulled[f["id"]] = {"local": os.path.basename(local),
                               "name": f["name"]}
            new += 1
            log(f"  new track: {f['name']}")
        except Exception as e:
            log(f"  could not download {f['name']}: {type(e).__name__}")
    return len(available())


def _safe(name):
    import re
    return re.sub(r"[^A-Za-z0-9._ -]", "_", os.path.basename(name)).strip()


def available():
    """Local track paths, sorted. Empty list means publish silent."""
    if not os.path.isdir(reel_config.MUSIC_DIR):
        return []
    return sorted(
        os.path.join(reel_config.MUSIC_DIR, n)
        for n in os.listdir(reel_config.MUSIC_DIR)
        if n.lower().endswith(reel_config.MUSIC_EXTS))


def choose(state):
    """Least-recently-used track, so the account does not sound repetitive."""
    tracks = available()
    if not tracks:
        return None
    recent = state.get("music_recent", [])
    fresh = [t for t in tracks
             if os.path.basename(t) not in
             recent[:reel_config.MUSIC_NO_REPEAT_WITHIN]]
    pool = fresh or tracks

    def last_used(path):
        try:
            return recent.index(os.path.basename(path))
        except ValueError:
            return len(recent) + 1
    pool.sort(key=lambda t: -last_used(t))
    return pool[0]


def remember(state, track):
    recent = state.setdefault("music_recent", [])
    recent.insert(0, os.path.basename(track))
    del recent[12:]


# ── mixing ──────────────────────────────────────────────────────────────────

def add_track(video_path, track_path, dest_path, duration):
    """Lay the track under the video, normalised, trimmed and faded out."""
    fade_start = max(0.0, duration - reel_config.MUSIC_FADE_OUT)
    af = (f"loudnorm=I={reel_config.MUSIC_TARGET_LUFS}:TP=-1.5:LRA=11,"
          f"afade=t=out:st={fade_start:.2f}:d={reel_config.MUSIC_FADE_OUT}")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-stream_loop", "-1", "-i", track_path,   # loop if the track is short
        "-filter_complex", f"[1:a]{af}[a]",
        "-map", "0:v:0", "-map", "[a]",
        "-c:v", "copy",                            # video already encoded
        "-c:a", "aac", "-b:a", "128k",
        "-shortest", "-movflags", "+faststart",
        dest_path,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"music mix failed: {out.stderr.strip()[-300:]}")
    return dest_path


def maybe_add(video_path, work_dir, info, state, decided=False):
    """Add music to this clip. Returns (path, meta_or_None). Never raises.

    decided=True means the CALLER has already settled the question — it has
    both the detection and Marcus's sheet override, which this module does not.
    Re-testing here would quietly overrule him, which is exactly what v1.0 did.
    decided=False keeps the old self-deciding behaviour for any other caller.

    NOTE ON WHAT "ADD" MEANS: the mix maps only the video stream and the new
    track, so any original audio is REPLACED, not layered under. That is the
    point on a clip whose own audio is wind or handling noise.
    """
    try:
        import video_host

        if not decided and reel_config.MUSIC_ONLY_WHEN_SILENT and \
                not video_host.is_effectively_silent(video_path, info):
            log("  video has real audio — leaving it alone")
            return video_path, None

        track = choose(state)
        if not track:
            log(f"  silent video and no tracks in the music folder — "
                f"publishing silent. Add licensed audio at "
                f"{reel_config.MUSIC_FOLDER_URL}")
            return video_path, None

        dest = os.path.join(work_dir, "with_music.mp4")
        log(f"  adding music: {os.path.basename(track)}")
        add_track(video_path, track, dest, info["duration"])
        new = video_host.probe(dest)
        ok, why = video_host.validate(new)
        if not ok:
            log(f"  mixed file failed validation ({why}) — publishing silent")
            return video_path, None

        remember(state, track)
        return dest, {"track": os.path.basename(track),
                      "lufs": reel_config.MUSIC_TARGET_LUFS}
    except Exception as e:
        log(f"  music step failed ({type(e).__name__}: {str(e)[:120]}) — "
            f"publishing the original")
        return video_path, None
