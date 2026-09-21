"""
image_host.py — put approved slides somewhere Instagram can fetch them
=============================================================================
VERSION 1.2 — 2026-08-25

WHY THIS EXISTS
    Meta does not accept image uploads. It FETCHES each image from a public
    URL, anonymously. That rules out every place Selene's images currently
    live:
      • Google Drive  — link formats that look public are not fetchable
      • selene-ig-memory — the repo is PRIVATE (unauthenticated GitHub
        returns 404), so raw.githubusercontent.com will not serve it
    So published slides get copied to a SECOND, PUBLIC repo used purely as a
    transient image host. Nothing secret goes in it; the images are about to
    be on a public Instagram feed anyway.

HARD RULES, all learned from real rejections during the 2026-08-21 smoke test
    • JPEG only. A PNG returns error 9004 / subcode 2207052,
      "Only photo or video can be accepted as media type".
    • ~8 MB ceiling. A 17 MB file was refused.
    • Aspect ratio must sit between 4:5 (0.80) and 1.91:1.
    Generated slides arrive as large PNGs — one source asset was 7432x4957
    and 16 MB — so converting is mandatory, not defensive.

METADATA IS STRIPPED, DELIBERATELY (v1.2)
    Nano Banana Pro embeds C2PA/XMP provenance metadata in every image, and
    Meta's "AI info" label keys off exactly that. Marcus was stripping it by
    hand (export as PNG, "preserve metadata" unchecked) before every manual
    post; the runner now does the equivalent automatically. The strip is a
    pure segment removal — APP1 (EXIF/XMP), APP11 (JUMBF/C2PA), APP13 (IPTC),
    other APPn and COM are dropped; JFIF, the ICC colour profile and the
    Adobe transform marker are kept; pixel data is untouched (verified
    byte-identical). NOTE: Google's SynthID pixel watermark survives any
    metadata strip — if Meta ever labels from classifiers instead of
    metadata, this stops working. Today, metadata is the trigger.

WHY sips AND NOT PILLOW
    Pillow is not installed on this Mac and adding a dependency to a pipeline
    that already fails on credentials is a bad trade. sips ships with macOS.
=============================================================================
"""

import base64
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

import config

GITHUB_USER = "leemarcusmz"
PUBLIC_REPO = "selene-ig-public"
PUBLIC_BRANCH = "main"

MAX_WIDTH = 1440          # Instagram's own display ceiling
JPEG_QUALITY = "high"     # sips: low | normal | high | best
MIN_RATIO = 0.80          # 4:5
MAX_RATIO = 1.91          # 1.91:1
MAX_BYTES = 8 * 1024 * 1024

TOKEN_FILE = os.path.join(config.BASE_DIR, "github_token.txt")


def log(msg):
    print(f"[image_host] {msg}", flush=True)


def _token():
    with open(TOKEN_FILE) as fh:
        return fh.read().strip()


# ── image preparation ───────────────────────────────────────────────────────

def _dimensions(path):
    out = subprocess.run(
        ["sips", "-g", "pixelWidth", "-g", "pixelHeight", path],
        capture_output=True, text=True, check=True).stdout
    w = h = None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("pixelWidth:"):
            w = int(line.split(":")[1])
        elif line.startswith("pixelHeight:"):
            h = int(line.split(":")[1])
    if not w or not h:
        raise RuntimeError(f"could not read dimensions of {path}")
    return w, h


def prepare(src_path, dest_path):
    """Convert to a JPEG Instagram will actually accept.

    Out-of-range aspect ratios are centre-cropped to the nearest allowed
    bound rather than rejected — Instagram would crop it anyway, and stalling
    a whole post over a slightly tall image helps nobody. The crop is logged
    so it is never silent.
    """
    subprocess.run(
        ["sips", "-s", "format", "jpeg", "-s", "formatOptions", JPEG_QUALITY,
         src_path, "--out", dest_path],
        capture_output=True, check=True)

    w, h = _dimensions(dest_path)
    ratio = w / h
    if ratio > MAX_RATIO:
        new_w = int(round(h * MAX_RATIO))
        log(f"  aspect {ratio:.2f} too wide — centre-cropping to {new_w}x{h}")
        subprocess.run(["sips", "--cropToHeightWidth", str(h), str(new_w), dest_path],
                       capture_output=True, check=True)
    elif ratio < MIN_RATIO:
        new_h = int(round(w / MIN_RATIO))
        log(f"  aspect {ratio:.2f} too tall — centre-cropping to {w}x{new_h}")
        subprocess.run(["sips", "--cropToHeightWidth", str(new_h), str(w), dest_path],
                       capture_output=True, check=True)

    w, h = _dimensions(dest_path)
    if w > MAX_WIDTH:
        subprocess.run(["sips", "--resampleWidth", str(MAX_WIDTH), dest_path],
                       capture_output=True, check=True)
        w, h = _dimensions(dest_path)

    stripped = strip_jpeg_metadata(dest_path)

    size = os.path.getsize(dest_path)
    if size > MAX_BYTES:
        raise RuntimeError(f"still {size/1e6:.1f} MB after conversion — too big for Instagram")
    log(f"  prepared {w}x{h} ({size/1024:.0f} KB, aspect {w/h:.2f}, "
        f"{stripped} metadata segment(s) stripped)")
    return dest_path


def strip_jpeg_metadata(path):
    """Remove metadata segments from a JPEG in place, without re-encoding.

    Drops APP1 (EXIF/XMP), APP11 (JUMBF — where C2PA manifests live),
    APP13 (IPTC), every other APPn except JFIF/ICC/Adobe, and COM comments.
    Keeps pixel data byte-identical. See the header for why this exists.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:2] != b"\xff\xd8":
        raise ValueError(f"{path} is not a JPEG")
    KEEP_APP = {0xE0, 0xE2, 0xEE}          # JFIF, ICC profile, Adobe transform
    out, i, removed = bytearray(b"\xff\xd8"), 2, 0
    while i < len(data) - 1:
        if data[i] != 0xFF:                 # malformed padding — keep the rest
            out += data[i:]
            break
        marker = data[i + 1]
        if marker == 0xDA:                  # SOS — scan data follows, copy all
            out += data[i:]
            break
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7 or marker == 0x01:
            out += data[i:i + 2]
            i += 2
            continue
        seglen = int.from_bytes(data[i + 2:i + 4], "big")
        seg = data[i:i + 2 + seglen]
        if (0xE0 <= marker <= 0xEF and marker not in KEEP_APP) or marker == 0xFE:
            removed += 1
        else:
            out += seg
        i += 2 + seglen
    with open(path, "wb") as fh:
        fh.write(bytes(out))
    return removed


# ── the public host ─────────────────────────────────────────────────────────

def _gh(method, path, payload=None):
    # NOTE: no trailing slash. f".../{PUBLIC_REPO}/{path}" with an empty path
    # yields ".../selene-ig-public/" and GitHub answers a trailing slash with
    # 404 — which made repo_exists() report False for a repo that plainly
    # existed and was public. Cost an evening on 2026-08-24.
    base = f"https://api.github.com/repos/{GITHUB_USER}/{PUBLIC_REPO}"
    req = urllib.request.Request(
        f"{base}/{path}" if path else base,
        data=json.dumps(payload).encode() if payload else None,
        method=method,
        headers={"Authorization": "Bearer " + _token(),
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read().decode()
        return r.status, (json.loads(body) if body else {})


def repo_exists():
    try:
        _gh("GET", "")
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


def raw_url(repo_path):
    return (f"https://raw.githubusercontent.com/{GITHUB_USER}/"
            f"{PUBLIC_REPO}/{PUBLIC_BRANCH}/{repo_path}")


def upload(local_path, repo_path):
    with open(local_path, "rb") as fh:
        content = base64.b64encode(fh.read()).decode()
    payload = {"message": f"publish: {repo_path}", "content": content}
    try:                                   # overwrite needs the existing sha
        _, meta = _gh("GET", f"contents/{repo_path}")
        if isinstance(meta, dict) and meta.get("sha"):
            payload["sha"] = meta["sha"]
    except urllib.error.HTTPError:
        pass
    _gh("PUT", f"contents/{repo_path}", payload)
    return raw_url(repo_path)


def wait_until_public(url, tries=10, delay=3):
    """Meta fetches anonymously and gets one shot. raw.githubusercontent can
    lag a few seconds behind the commit, so confirm the file is actually
    reachable before handing the URL to Instagram."""
    for i in range(tries):
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=20) as r:
                ctype = r.headers.get("Content-Type", "")
                if r.status == 200 and "image" in ctype:
                    return True
        except Exception:
            pass
        time.sleep(delay)
    return False


def host_slides(drive_service, file_ids, row_number, week):
    """Drive file ids -> public, Instagram-ready JPEG URLs, in order."""
    if not repo_exists():
        raise RuntimeError(
            f"the public image repo {GITHUB_USER}/{PUBLIC_REPO} does not exist yet. "
            f"Create it (public, with a README) at https://github.com/new — "
            f"Instagram cannot fetch images from the private selene-ig-memory repo.")

    from googleapiclient.http import MediaIoBaseDownload
    import io

    urls = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, fid in enumerate(file_ids, start=1):
            src = os.path.join(tmp, f"src_{i}")
            dst = os.path.join(tmp, f"slide_{i}.jpg")

            buf = io.BytesIO()
            downloader = MediaIoBaseDownload(
                buf, drive_service.files().get_media(fileId=fid))
            done = False
            while not done:
                _, done = downloader.next_chunk()
            with open(src, "wb") as fh:
                fh.write(buf.getvalue())

            prepare(src, dst)
            repo_path = f"posts/{week}/row{row_number}_slide{i}.jpg"
            url = upload(dst, repo_path)
            if not wait_until_public(url):
                raise RuntimeError(f"slide {i} did not become publicly reachable: {url}")
            log(f"  slide {i} hosted: {url}")
            urls.append(url)
    return urls
