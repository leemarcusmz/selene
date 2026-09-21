"""
hook_overlay.py — burn a hook line onto the opening of a video, legibly
=============================================================================
VERSION 2.4 — 2026-09-16

WHY THIS FILE IS MORE CAREFUL THAN IT LOOKS
    The carousel lane has an OPEN, UNFIXED bug: "PALE PHOTOS BREAK THE TYPE"
    (selene-edu-template-kit). Winter-white text is drawn with no scrim and a
    0.16 veil, which disappears over bright bedding. Selene shoots white linen
    in daylight, so that is not an edge case, it is the normal case.

    Video is worse than stills: brightness changes shot to shot, so a treatment
    chosen from one frame can fail two seconds later.

    So this module MEASURES rather than assumes. It samples the luminance of the
    exact band the text will occupy across the whole overlay window, and picks a
    treatment that survives the BRIGHTEST moment in that window, not the average.
    If even the strongest treatment cannot reach the contrast floor, it REFUSES
    and the caller falls back to a caption-mode hook. Illegible text is worse
    than no text.

    That measure-then-decide approach is the thing the carousel lane is missing.
    If it proves out here it should be back-ported to renderer_edu.

CHANGELOG
    2.4  2026-09-16  HOOK_DURATION=None keeps the hook up for the WHOLE clip
                     (fade-out still runs over the last HOOK_FADE seconds).
                     Marcus: the text "briefly appears and then disappears".
                     The band is now measured over the full shown duration.
    2.3  2026-09-11  render() accepts a band override. A clip composed with
                     reel_framing "fit" has an empty brand field above the
                     footage, which is a far better home for the hook than the
                     footage itself: Ecru on Moss Green measures 9.08:1, so no
                     scrim is needed and nothing is covered up. The caller
                     passes the field's geometry; the defaults are unchanged.
    2.2  2026-09-10  MEASURE THE BAND'S SPATIAL RANGE, NOT ITS AVERAGE.
                     The first render on Marcus's real footage was ILLEGIBLE:
                     ink text over a pale wall, crossing her dark hair and a
                     dark painting. v2.1 cropped the band and scaled it to ONE
                     pixel, so each sample was the band's spatial MEAN — a dark
                     object inside a mostly-pale band simply vanished. It
                     measured variation over TIME and missed variation across
                     the FRAME, which is the more common case by far.
                     Now each sample is a 16x4 grid, and a treatment must clear
                     the contrast floor against BOTH the darkest and the
                     brightest cell in the whole window. Flat colours therefore
                     only win on genuinely uniform bands; anything mixed goes
                     to a scrim, which is what normalises the range.
    2.1  2026-09-10  Pillow missing is now a FALLBACK, not a crash. v2.0 assumed
                     PIL was importable because renderer_edu uses it — but that
                     runs in the educational venv and this lane runs on system
                     python, so the first real run died with
                     "No module named 'PIL'" and parked the video. A missing
                     library should degrade to caption mode and say so loudly,
                     not stop the lane. Added to requirements.txt and to
                     --doctor, so it is caught before a run rather than during.
    2.0  2026-09-10  TEXT IS NOW RENDERED WITH PIL, NOT ffmpeg's drawtext.
                     Marcus's first overlay run died with "No such filter:
                     'drawtext'" — his ffmpeg was built without libfreetype.
                     Telling him to rebuild ffmpeg would have left the lane
                     depending on a compile flag nobody controls, so the text
                     and scrim are now drawn into one transparent RGBA PNG with
                     Pillow (already a dependency here — renderer_edu uses it)
                     and composited with ffmpeg's `overlay`, which every build
                     has.
                     Two things got better on the way: the scrim is a REAL
                     vertical gradient instead of the 24 stacked drawboxes that
                     approximated one, and text metrics come from the font
                     itself, so wrapping is measured rather than guessed at
                     26 characters.
    1.0  2026-09-09  First build.
=============================================================================
"""

import json
import os
import shutil
import subprocess

import reel_config

# Contrast floor. WCAG AA for large text is 3.0:1; 4.5 is AA for body text.
# Reels are watched small, in bright rooms, at a glance — so we hold the
# stricter line even though the type is large.
MIN_CONTRAST = 4.5

WINTER_WHITE = (0xF7, 0xF5, 0xEF)
INK = (0x2B, 0x2B, 0x28)


def log(msg):
    print(f"[hook_overlay] {msg}", flush=True)


# ── contrast maths (WCAG) ───────────────────────────────────────────────────

def _srgb_to_linear(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb):
    r, g, b = (_srgb_to_linear(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(rgb_a, rgb_b):
    la, lb = relative_luminance(rgb_a), relative_luminance(rgb_b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# ── measurement ─────────────────────────────────────────────────────────────

GRID_W, GRID_H = 16, 4     # spatial resolution of each band sample


def measure_band(video_path, y_frac, height_frac, duration, samples=8):
    """Luminance RANGE of the text band, across time AND across the frame.

    Returns (darkest_rgb, brightest_rgb). Each time sample is a GRID_W x GRID_H
    grid, not a single averaged pixel: text runs the full width of the band, so
    one dark object inside a pale band (a head of dark hair, a doorway, a
    painting) is exactly what makes a flat colour fail. Averaging hides it.
    """
    cells = []
    for i in range(samples):
        t = duration * (i + 0.5) / samples
        out = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", video_path,
             "-frames:v", "1",
             "-vf", (f"crop=iw:ih*{height_frac}:0:ih*{y_frac},"
                     f"scale={GRID_W}:{GRID_H},format=rgb24"),
             "-f", "rawvideo", "-"],
            capture_output=True)
        if out.returncode == 0 and len(out.stdout) >= GRID_W * GRID_H * 3:
            raw = out.stdout
            for c in range(GRID_W * GRID_H):
                cells.append(tuple(raw[c * 3:c * 3 + 3]))

    if not cells:
        raise RuntimeError("could not sample the video's luminance")

    darkest = min(cells, key=relative_luminance)
    brightest = max(cells, key=relative_luminance)
    return darkest, brightest


def choose_treatment(darkest, brightest):
    """Lightest treatment that clears the floor against the WHOLE band.

    A flat colour has to survive both extremes the text crosses. Ink needs the
    band's DARKEST cell still bright enough; winter white needs the BRIGHTEST
    cell still dark enough. A band containing both fails each of them, which is
    precisely when a scrim earns its visual cost — it compresses the range.
    """
    # 1. Ink, no scrim. Needs a uniformly BRIGHT band: the darkest thing the
    #    text crosses still has to contrast against dark type.
    if contrast_ratio(INK, darkest) >= MIN_CONTRAST:
        return {"name": "ink_no_scrim", "color": INK, "scrim": 0.0}

    # 2. Winter white, no scrim. Needs a uniformly DARK band.
    if contrast_ratio(WINTER_WHITE, brightest) >= MIN_CONTRAST:
        return {"name": "white_no_scrim", "color": WINTER_WHITE, "scrim": 0.0}

    # 3-5. Escalating scrim under winter white. Judged against the BRIGHTEST
    #      cell, because that is where white type is hardest to see.
    for alpha in (0.28, 0.42, 0.55):
        blended = tuple(int(c * (1 - alpha)) for c in brightest)
        if contrast_ratio(WINTER_WHITE, blended) >= MIN_CONTRAST:
            return {"name": f"white_scrim_{alpha}", "color": WINTER_WHITE,
                    "scrim": alpha}

    return None      # caller falls back to caption mode


# ── rendering ───────────────────────────────────────────────────────────────

def find_font():
    for path in reel_config.HOOK_FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    raise RuntimeError(
        "no hook font found. Tried: "
        + ", ".join(reel_config.HOOK_FONT_CANDIDATES))


def wrap(text, max_chars):
    """Character-count fallback, used only when a font cannot be measured."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if len(trial) <= max_chars:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def wrap_measured(text, font, max_px):
    """Wrap against the REAL rendered width. A 26-character rule is a guess;
    "Illinois" and "WWWWWWWW" are not the same width in any real typeface."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if font.getbbox(trial)[2] <= max_px:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def build_text_layer(lines, font, color, scrim, size, w, h,
                     y_frac=None, band_frac=None):
    """One transparent RGBA PNG carrying the scrim gradient and the text.

    Drawn with Pillow so the lane does not depend on how ffmpeg was compiled.
    """
    from PIL import Image, ImageDraw

    y_frac = reel_config.HOOK_Y_FRAC if y_frac is None else y_frac
    band_frac = reel_config.HOOK_BAND_FRAC if band_frac is None else band_frac

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    if scrim > 0:
        # A TRUE vertical gradient. v1.0 stacked 24 drawboxes to fake one
        # because ffmpeg had no better primitive; Pillow just draws it.
        pad = band_frac * 0.55
        top = max(0.0, y_frac - pad)
        height = min(1.0 - top, band_frac + pad * 2)
        y0, y1 = int(h * top), int(h * (top + height))
        grad = Image.new("RGBA", (1, max(1, y1 - y0)), (0, 0, 0, 0))
        gpx = grad.load()
        span = max(1, y1 - y0)
        for y in range(span):
            pos = (y + 0.5) / span
            weight = (1.0 - abs(pos - 0.5) * 2) ** 0.65
            gpx[0, y] = (0, 0, 0, int(255 * scrim * weight))
        layer.alpha_composite(grad.resize((w, span)), (0, y0))

    draw = ImageDraw.Draw(layer)
    line_h = int(size * 1.28)
    total_h = line_h * len(lines)
    band_top = h * y_frac
    band_h = h * band_frac
    y = band_top + (band_h - total_h) / 2

    for line in lines:
        bbox = font.getbbox(line)
        x = (w - (bbox[2] - bbox[0])) / 2 - bbox[0]
        draw.text((x, y), line, font=font, fill=color + (255,))
        y += line_h

    return layer


def render(video_path, hook_text, dest_path, info, band=None):
    """Burn the hook in. Returns a dict describing what was done, or None if
    the footage cannot carry legible text (caller falls back to caption mode).

    band, when given, is {"y_frac", "band_frac"} from reel_framing — the empty
    brand field above a fitted clip. Measuring THAT strip rather than the
    default one is the whole point: it is a flat known colour, so the treatment
    chosen is the one that actually sits behind the words.
    """
    wanted = reel_config.HOOK_DURATION
    duration = (info["duration"] if wanted is None
                else min(float(wanted), info["duration"]))
    y_frac = (band or {}).get("y_frac", reel_config.HOOK_Y_FRAC)
    band_h = (band or {}).get("band_frac", reel_config.HOOK_BAND_FRAC)

    darkest, brightest = measure_band(video_path, y_frac, band_h, duration)
    treatment = choose_treatment(darkest, brightest)

    if treatment is None:
        log(f"  REFUSING overlay: band is too mixed to hold legible text "
            f"(range rgb{darkest} to rgb{brightest})")
        return None

    log(f"  band range rgb{darkest} to rgb{brightest} -> {treatment['name']}")

    font_path = find_font()
    size = int(info["width"] * reel_config.HOOK_SIZE_FRAC)

    try:
        from PIL import ImageFont
    except ImportError:
        # Degrade, do not die. An unavailable renderer must not park a video
        # forever; the run falls back to a caption-mode hook and publishes.
        log("  Pillow is NOT INSTALLED for this python, so the hook cannot be "
            "drawn. Falling back to caption mode.")
        log("     Fix: python3 -m pip install pillow")
        log("     (add --break-system-packages if pip refuses on homebrew python)")
        return None

    try:
        font = ImageFont.truetype(font_path, size)
        lines = wrap_measured(hook_text, font,
                              int(info["width"] * reel_config.HOOK_TEXT_WIDTH))
    except Exception as e:
        log(f"  could not load the hook font {font_path}: {e}")
        log("  falling back to caption mode")
        return None

    if len(lines) > reel_config.HOOK_MAX_LINES:
        log(f"  hook needs {len(lines)} lines, max is "
            f"{reel_config.HOOK_MAX_LINES} — refusing")
        return None

    layer_path = os.path.join(os.path.dirname(dest_path), "hook_layer.png")
    layer = build_text_layer(lines, font, treatment["color"],
                             treatment["scrim"], size,
                             info["width"], info["height"],
                             y_frac=y_frac, band_frac=band_h)
    layer.save(layer_path)

    fade = reel_config.HOOK_FADE
    # Fade the LAYER's alpha, then composite. `overlay` exists in every ffmpeg
    # build; `drawtext` needs libfreetype, which Marcus's build lacks.
    filters = [
        f"[1:v]format=rgba,"
        f"fade=t=in:st=0:d={fade}:alpha=1,"
        f"fade=t=out:st={max(0.0, duration - fade):.2f}:d={fade}:alpha=1[hk]",
        f"[0:v][hk]overlay=0:0:enable='between(t,0,{duration:.2f})'[v]",
    ]

    cmd = ["ffmpeg", "-y", "-i", video_path, "-loop", "1", "-i", layer_path,
           "-filter_complex", ";".join(filters), "-map", "[v]"]
    if info.get("has_audio"):
        cmd += ["-map", "0:a", "-c:a", "copy"]
    else:
        cmd += ["-an"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-t", f"{info['duration']:.3f}", dest_path]

    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"overlay render failed: {out.stderr.strip()[-400:]}")

    log(f"  rendered overlay: \"{hook_text}\" ({len(lines)} line(s))")
    return {
        "treatment": treatment["name"],
        "scrim": treatment["scrim"],
        "lines": lines,
        "band_darkest": list(darkest),
        "band_brightest": list(brightest),
        # Report the WORST contrast the text actually faces, not the best.
        "contrast": round(min(
            contrast_ratio(treatment["color"],
                           tuple(int(c * (1 - treatment["scrim"])) for c in darkest)),
            contrast_ratio(treatment["color"],
                           tuple(int(c * (1 - treatment["scrim"])) for c in brightest))), 2),
    }
