"""
reel_framing.py — put any aspect ratio on a 9:16 phone screen, deliberately
=============================================================================
VERSION 1.1 — 2026-09-16

THE PROBLEM
    Marcus's New Zealand shoot is 16:9. A reel is viewed at 9:16 on a phone.
    Three ways to bridge that, and they are not equivalent:

      CROP   keep 9:16 out of the middle. Of a 16:9 source that keeps
             (9/16)/(16/9) = 81/256 of the width — 32%, DISCARDING 68%.
             Right for a tight shot where the subject fills the frame.
             Wrong for a wide landscape: on "bed on a beach", the beach IS
             the shot, and cropping to the bed deletes the idea.

      FIT    the whole 16:9 frame, full width, on a 9:16 brand field. Loses
             nothing. The space above and below is not wasted — it is where
             the hook goes, which is the one piece of this lane that has never
             had a good home. On a cropped frame the hook sits ON the footage
             and needs a scrim to stay legible; here it sits on Moss Green at
             ~9:1 contrast and needs nothing.

      NONE   the source is already 9:16. Touch nothing.

    What this module deliberately does NOT do is generate the missing edges.
    An AI expansion would invent ceiling, floor, room and bedding above and
    below real product footage. For a brand that keeps claims_edu.md as the
    single source of truth about what its products are, inventing product
    imagery is the same error in pictures.

WHY FIT IS THE DEFAULT
    Because it cannot destroy anything. A wrong crop is unrecoverable and
    invisible until you watch the output; a wrong fit is merely less punchy.
    Unattended, the safe failure is the right default. Override per video in
    the Videos tab — same one-minute pass as text and audio.

CHANGELOG
    1.1  2026-09-16  Fitted clips: the hook can sit BELOW the footage
                     (reel_config.FIT_HOOK_POSITION), in the lower brand
                     field, capped at IG_SAFE_BOTTOM_FRAC so it never runs
                     under Instagram's caption UI. Default is now below;
                     "above" keeps the 1.0 layout. plan() also reports
                     hook_position for the log.
    1.0  2026-09-11  First build.
=============================================================================
"""

import os
import subprocess

import reel_config

VERSION = "1.1"

MODES = ("crop", "fit", "none")


def log(msg):
    print(f"[reel_framing] {msg}", flush=True)


def _hex_to_ffmpeg(h):
    return "0x" + h.lstrip("#").upper()


def is_vertical_enough(info):
    """True when the source is already close enough to 9:16 to leave alone."""
    ratio = info["width"] / info["height"]
    target = reel_config.CANVAS_W / reel_config.CANVAS_H
    return abs(ratio - target) <= reel_config.FRAMING_RATIO_TOLERANCE


def decide(info, setting=None):
    """Which treatment this clip gets. Returns one of MODES.

    setting is Marcus's Videos-tab answer: "crop", "fit", or None for auto.
    An explicit answer wins even on an already-vertical clip, because he may
    want a 9:16 source letterboxed smaller to make room for the hook.
    """
    if setting in ("crop", "fit"):
        return setting
    return "none" if is_vertical_enough(info) else reel_config.FRAMING_DEFAULT


def plan(info, mode):
    """Geometry for one clip, without running anything. Returns a dict.

    Separated from the render so the numbers can be asserted in tests without
    ffmpeg, and so --sample can print them.
    """
    W, H = reel_config.CANVAS_W, reel_config.CANVAS_H
    sw, sh = info["width"], info["height"]

    if mode == "none":
        return {"mode": "none", "hook_y_frac": reel_config.HOOK_Y_FRAC,
                "hook_band_frac": reel_config.HOOK_BAND_FRAC,
                "hook_on_field": False}

    if mode == "crop":
        # Scale so the HEIGHT fills the canvas, then take the middle 1080.
        scaled_w = int(round(sw * H / sh))
        x = int(round((scaled_w - W) * reel_config.CROP_X_FRAC))
        return {"mode": "crop", "scaled_w": scaled_w, "scaled_h": H,
                "crop_x": max(0, x), "kept_width_pct": round(W / scaled_w * 100),
                "hook_y_frac": reel_config.HOOK_Y_FRAC,
                "hook_band_frac": reel_config.HOOK_BAND_FRAC,
                "hook_on_field": False}

    # fit: full width, centred vertically, brand field above and below
    vid_h = int(round(W * sh / sw))
    vid_h -= vid_h % 2
    if vid_h >= H:                      # taller than the canvas: nothing to fit
        return plan(info, "crop")
    top = int(round((H - vid_h) * reel_config.FIT_VIDEO_Y_FRAC))
    top -= top % 2
    band_top_h = top
    band_bottom_h = H - vid_h - top
    position = getattr(reel_config, "FIT_HOOK_POSITION", "above")
    gap = getattr(reel_config, "FIT_HOOK_GAP_PX", 40)
    safe_bottom = int(H * getattr(reel_config, "IG_SAFE_BOTTOM_FRAC", 0.76))
    below_room = safe_bottom - (top + vid_h) - gap
    if position == "below" and below_room >= int(H * 0.08):
        # Under the footage, above Instagram's caption strip. Reads like a
        # caption card; keeps the picture itself clean.
        hook_y = top + vid_h + gap
        hook_band = min(below_room, int(H * reel_config.HOOK_BAND_FRAC))
    else:
        # 1.0 layout: the middle of the upper field, not against an edge.
        position = "above"
        hook_band = band_top_h * reel_config.FIT_HOOK_BAND_SHARE
        hook_y = (band_top_h - hook_band) / 2
    return {"mode": "fit", "vid_h": vid_h, "top": top,
            "band_top_h": band_top_h, "band_bottom_h": band_bottom_h,
            "hook_y_frac": round(hook_y / H, 4),
            "hook_band_frac": round(hook_band / H, 4),
            "hook_position": position,
            "hook_on_field": True}


def render(src, dest, info, mode):
    """Produce the 9:16 file. Returns meta, or None when nothing was needed."""
    p = plan(info, mode)
    if p["mode"] == "none":
        return None

    W, H = reel_config.CANVAS_W, reel_config.CANVAS_H

    if p["mode"] == "crop":
        vf = (f"scale={p['scaled_w']}:{H}:flags=lanczos,"
              f"crop={W}:{H}:{p['crop_x']}:0")
    else:
        field = _hex_to_ffmpeg(reel_config.FIT_FIELD_COLOUR)
        vf = (f"scale={W}:{p['vid_h']}:flags=lanczos,"
              f"pad={W}:{H}:0:{p['top']}:color={field}")

    cmd = ["ffmpeg", "-y", "-i", src, "-vf", vf,
           "-c:v", "libx264", "-crf", str(reel_config.FRAMING_CRF),
           "-preset", "medium", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart"]
    # Keep the audio exactly as it was: this is a picture operation.
    cmd += (["-c:a", "copy"] if info.get("has_audio") else ["-an"])
    cmd += [dest]

    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"framing failed: {out.stderr.strip()[-300:]}")

    p["src_ratio"] = round(info["width"] / info["height"], 3)
    return p


def describe(p):
    """One human line for the log and the sheet."""
    if p is None or p["mode"] == "none":
        return "already 9:16"
    if p["mode"] == "crop":
        return f"crop, keeps {p['kept_width_pct']}% of frame width"
    return (f"fit on brand field, {p['band_top_h']}px above / "
            f"{p['band_bottom_h']}px below, hook {p.get('hook_position', 'above')} "
            f"the footage")


# =============================================================================
# SAMPLE — render every mode side by side so a default can be CHOSEN, not argued
# =============================================================================

def sample(src, out_dir=None):
    import video_host
    info = video_host.probe(src)
    out_dir = out_dir or os.path.join(reel_config.REEL_ROOT, "_Framing Samples")
    os.makedirs(out_dir, exist_ok=True)

    stem = os.path.splitext(os.path.basename(src))[0]
    print(f"\n{stem}: {info['width']}x{info['height']} "
          f"(ratio {info['width'] / info['height']:.2f}), "
          f"{info['duration']:.1f}s\n")

    made = []
    for mode in ("crop", "fit"):
        p = plan(info, mode)
        dest = os.path.join(out_dir, f"{stem} [{mode}].mp4")
        print(f"  {mode:<5} {describe(p)}")
        try:
            render(src, dest, info, mode)
            made.append(dest)
        except Exception as e:
            print(f"        FAILED: {e}")
    print(f"\n{out_dir}\n")
    return made


if __name__ == "__main__":
    import sys
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print(__doc__.split("CHANGELOG")[0])
        print("Usage: python3 reel_framing.py <video file>")
        sys.exit(1)
    sample(args[0])
