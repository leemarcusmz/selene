"""
video_host.py — put a video somewhere Meta can fetch it, exactly once
=============================================================================
VERSION 1.3 — 2026-09-11

WHY THIS EXISTS
    Meta does not accept an upload. It accepts a URL, fetches it anonymously,
    and gets ONE shot at it. image_host.py already solved this for stills by
    pushing to the public GitHub repo; this is the same trick for video, with
    the validation image_host does not need.

WHAT IT WILL NOT DO
    It will not silently re-encode Marcus's video to make it fit. If a file
    breaks Meta's spec it is REJECTED with a reason, because a re-encode we
    never looked at is a worse outcome than a skipped post. The one exception
    is container remuxing (.mov -> .mp4) which is lossless and unambiguous.

CHANGELOG
    1.3  2026-09-11  validate() takes a STAGE. A source file is judged against
                     what we will download (MAX_SOURCE_BYTES); a delivery file
                     against what we will host (MAX_BYTES). Before this the
                     hosting cap was applied to the source, BEFORE the
                     downscale that exists to get under it — so a 105 MB 4K
                     master was refused for being too big to host, without ever
                     being given the chance to shrink.
    1.2  2026-09-09  measure_loudness()/is_effectively_silent(). The first live
                     reel published with no sound: the DJI source carried a real
                     AAC stereo track whose CONTENT was digital silence (mean
                     AND max both -91 dB). A present audio stream is not the
                     same as audible audio, and has_audio could not tell the
                     difference. reel_music uses this to decide whether adding a
                     track would be filling a silence or destroying real sound.
    1.1  2026-09-09  DELIVERY DOWNSCALE. The first real video was a 48.5 MB
                     drone master: 1728x3072 at 35 Mbps, for an 11 second clip.
                     Instagram serves reels at roughly 1080x1920 and ~5 Mbps and
                     transcodes everything anyway, so every byte above that was
                     pure cost — a 64.7 MB base64 payload in ONE JSON PUT to
                     GitHub, plus a slow Meta fetch, for zero visible quality.
                     Oversized or over-bitrate video is now re-encoded to
                     1080-wide before hosting. This is a DELIVERY step and is
                     always logged; it is not the silent spec-fixing that the
                     note below still refuses to do.
    1.0  2026-09-09  First build.
=============================================================================
"""

import base64
import json
import os
import subprocess
import time
import urllib.error
import urllib.request

import config
import reel_config

GITHUB_USER = "leemarcusmz"
PUBLIC_REPO = "selene-ig-public"
PUBLIC_BRANCH = "main"

# What Instagram actually serves a reel at. Anything above this is transcoded
# by Meta regardless, so shipping more is upload cost and fetch latency for no
# visible gain. The first real video was a 48.5 MB drone master at 35 Mbps.
DELIVERY_WIDTH = 1080
DELIVERY_CRF = "21"          # visually transparent at this size
DELIVERY_MAX_MBPS = 12.0     # re-encode above this even if the width is fine

TOKEN_FILE = os.path.join(config.BASE_DIR, "github_token.txt")


def log(msg):
    print(f"[video_host] {msg}", flush=True)


def _token():
    with open(TOKEN_FILE) as fh:
        return fh.read().strip()


# ── inspection ──────────────────────────────────────────────────────────────

def probe(path):
    """Return a dict of what ffprobe knows. Raises on an unreadable file."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", path],
        capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {out.stderr.strip()[:300]}")
    data = json.loads(out.stdout)

    video = next((s for s in data.get("streams", [])
                  if s.get("codec_type") == "video"), None)
    if video is None:
        raise RuntimeError("no video stream in file")
    audio = next((s for s in data.get("streams", [])
                  if s.get("codec_type") == "audio"), None)

    w = int(video.get("width") or 0)
    h = int(video.get("height") or 0)
    duration = float(data.get("format", {}).get("duration") or 0.0)

    return {
        "width": w,
        "height": h,
        "ratio": (w / h) if h else 0.0,
        "duration": duration,
        "vcodec": video.get("codec_name"),
        "acodec": audio.get("codec_name") if audio else None,
        "has_audio": audio is not None,
        "bytes": os.path.getsize(path),
    }


SILENCE_DBFS = -50.0     # below this there is nothing a viewer could hear


def measure_loudness(path):
    """Peak dBFS of the audio, or None when there is no audio at all.

    ffprobe reports the STREAM; this reports whether anything is in it.
    """
    out = subprocess.run(
        ["ffmpeg", "-i", path, "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True)
    for line in out.stderr.split("\n"):
        if "max_volume:" in line:
            try:
                return float(line.split("max_volume:")[1].strip().split()[0])
            except (ValueError, IndexError):
                return None
    return None


def is_effectively_silent(path, info=None):
    """True when this video has nothing a viewer would hear."""
    info = info or probe(path)
    if not info["has_audio"]:
        return True
    peak = measure_loudness(path)
    return peak is None or peak <= SILENCE_DBFS


def validate(info, stage="delivery"):
    """Return (ok, reason). Reason is human-readable and goes in the log.

    stage="source"   judge the file we are about to PROCESS
    stage="delivery" judge the file we are about to HOST (the default, so
                     every existing caller keeps its old meaning)
    """
    if info["duration"] < reel_config.MIN_DURATION:
        return False, f"{info['duration']:.1f}s is under Meta's 3s floor"
    if info["duration"] > reel_config.MAX_DURATION:
        return False, f"{info['duration']:.0f}s is over Meta's 15 min ceiling"
    cap = (reel_config.MAX_SOURCE_BYTES if stage == "source"
           else reel_config.MAX_BYTES)
    if info["bytes"] > cap:
        mb = info["bytes"] / 1024 / 1024
        label = "download cap" if stage == "source" else "hosting cap"
        return False, f"{mb:.0f} MB is over the {cap // 1024 // 1024} MB {label}"
    if not (reel_config.MIN_RATIO <= info["ratio"] <= reel_config.MAX_RATIO):
        return False, f"aspect ratio {info['ratio']:.2f} outside Meta's range"
    if info["vcodec"] != "h264":
        return False, f"video codec is {info['vcodec']}, Meta wants h264"
    if info["has_audio"] and info["acodec"] != "aac":
        return False, f"audio codec is {info['acodec']}, Meta wants aac"
    return True, "ok"


def remux_to_mp4(src, dest):
    """Lossless container change. Streams are copied, never re-encoded."""
    out = subprocess.run(
        ["ffmpeg", "-y", "-i", src, "-c", "copy",
         "-movflags", "+faststart", dest],
        capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"remux failed: {out.stderr.strip()[-300:]}")
    return dest


def needs_downscale(info):
    """Is this bigger or fatter than Instagram will ever show? (reason or None)"""
    if info["width"] > DELIVERY_WIDTH:
        return f"{info['width']}px wide (Instagram shows {DELIVERY_WIDTH})"
    if info["duration"] > 0:
        mbps = info["bytes"] * 8 / info["duration"] / 1_000_000
        if mbps > DELIVERY_MAX_MBPS:
            return f"{mbps:.0f} Mbps (delivery ceiling {DELIVERY_MAX_MBPS:.0f})"
    return None


def downscale(src, dest, info):
    """Re-encode to delivery size. Keeps the aspect ratio, never upscales."""
    # -2 keeps the aspect and forces an even height, which H.264 requires.
    scale = (f"scale={DELIVERY_WIDTH}:-2"
             if info["width"] > DELIVERY_WIDTH else "scale=iw:-2")
    cmd = ["ffmpeg", "-y", "-i", src, "-vf", scale,
           "-c:v", "libx264", "-preset", "medium", "-crf", DELIVERY_CRF,
           "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    cmd += ["-c:a", "aac", "-b:a", "128k"] if info.get("has_audio") else ["-an"]
    cmd += [dest]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"downscale failed: {out.stderr.strip()[-300:]}")
    return dest


def prepare(src_path, work_dir):
    """Validate, then remux or downscale for delivery. Returns (path, info)."""
    info = probe(src_path)
    ok, reason = validate(info, stage="source")
    if not ok:
        raise ValueError(reason)

    os.makedirs(work_dir, exist_ok=True)

    why = needs_downscale(info)
    if why:
        dest = os.path.join(work_dir, "delivery.mp4")
        before = info["bytes"] / 1024 / 1024
        log(f"downscaling for delivery: {why}")
        downscale(src_path, dest, info)
        new = probe(dest)
        after = new["bytes"] / 1024 / 1024
        log(f"  {before:.1f} MB {info['width']}x{info['height']} -> "
            f"{after:.1f} MB {new['width']}x{new['height']} "
            f"({(1 - after / before) * 100:.0f}% smaller)")
        # A downscale that made things worse is a bug, not an optimisation.
        if new["bytes"] >= info["bytes"]:
            log("  re-encode did not shrink the file — keeping the original")
        else:
            ok, reason = validate(new, stage="delivery")
            if not ok:
                raise ValueError(f"even after downscaling, {reason}")
            return dest, new

    ok, reason = validate(info, stage="delivery")
    if not ok:
        # Under the download cap, over the hosting cap, and the downscale rules
        # did not fire. Force one: this is what the downscale is FOR.
        dest = os.path.join(work_dir, "delivery.mp4")
        log(f"{reason} — re-encoding to get under it")
        downscale(src_path, dest, info)
        new = probe(dest)
        ok, reason = validate(new, stage="delivery")
        if not ok:
            raise ValueError(f"even after downscaling, {reason}")
        return dest, new

    if src_path.lower().endswith(".mp4"):
        return src_path, info

    dest = os.path.join(work_dir, "prepared.mp4")
    log(f"remuxing {os.path.basename(src_path)} to mp4 (no re-encode)")
    remux_to_mp4(src_path, dest)
    return dest, probe(dest)


# ── hosting ─────────────────────────────────────────────────────────────────

def _gh(method, path, payload=None):
    base = f"https://api.github.com/repos/{GITHUB_USER}/{PUBLIC_REPO}"
    url = f"{base}/{path}" if path else base
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {_token()}")
    req.add_header("Accept", "application/vnd.github+json")
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode() or "{}")


def raw_url(repo_path):
    return (f"https://raw.githubusercontent.com/{GITHUB_USER}/"
            f"{PUBLIC_REPO}/{PUBLIC_BRANCH}/{repo_path}")


def upload(local_path, repo_path):
    """Create or overwrite a file in the public repo. Returns its raw URL."""
    with open(local_path, "rb") as fh:
        content = base64.b64encode(fh.read()).decode()

    payload = {
        "message": f"trial reel asset {repo_path}",
        "content": content,
        "branch": PUBLIC_BRANCH,
    }
    try:
        existing = _gh("GET", f"contents/{repo_path}")
        if isinstance(existing, dict) and existing.get("sha"):
            payload["sha"] = existing["sha"]
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise

    _gh("PUT", f"contents/{repo_path}", payload)
    return raw_url(repo_path)


def wait_until_public(url, tries=15, delay=4):
    """Meta gets one anonymous fetch. Do not hand it a URL that 404s yet."""
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        if attempt < tries:
            time.sleep(delay)
    return False


def host(local_path, slug):
    """Full path: upload the prepared video, confirm it serves, return URL."""
    repo_path = f"{reel_config.PUBLIC_REPO_PREFIX}/{slug}.mp4"
    url = upload(local_path, repo_path)
    log(f"uploaded -> {url}")
    if not wait_until_public(url):
        raise RuntimeError(f"hosted video never became publicly fetchable: {url}")
    log("confirmed publicly fetchable")
    return url
