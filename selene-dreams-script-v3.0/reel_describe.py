"""
reel_describe.py — look at the video so Marcus never has to describe it
=============================================================================
VERSION 1.0 — 2026-09-09

THE PROBLEM THIS SOLVES
    Marcus wants to drop a file and walk away. But the caption writer has
    always been handed a product row (fabric, type, variant) plus images it
    could see. A dropped video carries none of that.

HOW
    Extract evenly-spaced frames with ffmpeg, drop them in a work directory,
    and invoke the Claude Code CLI there to LOOK at them — the same headless
    vision pattern screen_runner.py uses for shortlist scoring. It returns a
    structured description: what is on screen, which Selene product (if any),
    the mood, and the strongest hook moment.

WHY A SEPARATE PASS FROM CAPTIONING
    Two reasons. Description is reusable across re-posts of the same video, so
    it is cached in state and never paid for twice. And a description that is
    wrong is visible in the log as a description, instead of being invisibly
    baked into a caption nobody reviewed.

CHANGELOG
    1.0  2026-09-09  First build.
=============================================================================
"""

import json
import os
import subprocess

import reel_config
from claude_client import invoke_claude_json


def log(msg):
    print(f"[reel_describe] {msg}", flush=True)

DESCRIBE_SCHEMA = {
    "summary":          {"type": "str"},
    "on_screen":        {"type": "str"},
    "product_guess":    {"type": "str"},
    "fabric_guess":     {"type": "str"},
    "mood":             {"type": "str"},
    "hook":             {"type": "str"},
    "has_text_overlay": {"type": "bool"},
    "has_people":       {"type": "bool"},
    "seo_terms":        {"type": "list", "min_len": 3},
}


def extract_frames(video_path, work_dir, count=None):
    """Evenly spaced stills. Returns the list of frame paths written."""
    count = count or reel_config.FRAME_COUNT
    os.makedirs(work_dir, exist_ok=True)

    import video_host
    duration = video_host.probe(video_path)["duration"]

    paths = []
    for i in range(count):
        # Sample inside the clip, never the very first or last frame: both
        # are routinely black or a fade.
        t = duration * (i + 0.5) / count
        dest = os.path.join(work_dir, f"frame_{i + 1:02d}.jpg")
        out = subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", video_path,
             "-frames:v", "1", "-vf", "scale=768:-2", "-q:v", "4", dest],
            capture_output=True, text=True)
        if out.returncode == 0 and os.path.exists(dest):
            paths.append(dest)

    if not paths:
        raise RuntimeError("ffmpeg extracted no frames from the video")
    log(f"  extracted {len(paths)} frames for the vision pass")
    return paths


def build_prompt(frame_paths, info, filename, out_path):
    names = "\n".join(f"  - {os.path.basename(p)}" for p in frame_paths)
    seconds = f"{info['duration']:.1f}"
    shape = ("vertical" if info["ratio"] < 0.95
             else "square" if info["ratio"] < 1.1 else "horizontal")
    return f"""You are looking at frames sampled in order from a short video that
Selene Dreams is about to publish as an Instagram trial reel.

Selene Dreams sells premium bedding: mulberry silk and linen sheet sets, duvet
covers, pillowcases, eye masks. Quiet-luxury register, calm interiors.

The video file is "{filename}". It runs {seconds} seconds, {shape}
({info['width']}x{info['height']}), audio: {'yes' if info['has_audio'] else 'none'}.

Read these frames, in this order, from the current directory:
{names}

Describe what is ACTUALLY on screen. Do not invent product details you cannot
see. If you cannot tell which product it is, say so plainly in product_guess
rather than guessing a plausible one — a wrong product name in a caption is
worse than a vague one.

Write JSON to the output path with exactly these keys:
  summary          one sentence: what this video shows, start to finish
  on_screen        the concrete visual content: objects, setting, light, motion
  product_guess    the Selene product visible, or "unclear" if you cannot tell
  fabric_guess     "silk", "linen", "unclear", or "none visible"
  mood             three or four words for the register (e.g. "still, warm, morning")
  hook             the single strongest opening moment and why it would stop a scroll
  has_text_overlay true if any frame carries burned-in words
  has_people       true if a person appears
  seo_terms        4-8 lowercase search phrases a cold viewer might actually
                   type that this video genuinely answers. Concrete, not
                   aspirational: "silk pillowcase for hair" not "luxury living".

OUTPUT: write EXACTLY one JSON object to {out_path} with the Write tool,
then stop. No commentary, no other files."""


def describe(video_path, info, work_dir):
    """Returns the description dict. Raises if the vision pass fails."""
    os.makedirs(work_dir, exist_ok=True)
    frames = extract_frames(video_path, work_dir)

    out_path = os.path.join(work_dir, "description.json")
    prompt = build_prompt(frames, info, os.path.basename(video_path), out_path)

    ok, result = invoke_claude_json(
        prompt, work_dir, out_path,
        schema=DESCRIBE_SCHEMA, stage="screening", timeout=420)

    if not ok:
        raise RuntimeError(f"vision pass failed: {result}")

    log(f"  described: {result.get('summary', '')[:110]}")
    return result
