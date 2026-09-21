"""
taste_brief.py — distill the taste layer into ONE brief every writer reads
=============================================================================
VERSION 1.2 — 2026-09-16

WHAT
    taste/references.md, feedback.md and outcomes.md (taste_store) are raw.
    This turns them into taste/brief.md: a short list of PRINCIPLES about what
    Marcus wants, that every writer in every lane receives as {taste_brief}:
    image prompts, the Monday screener, image captions, reel hooks, reel
    captions, educational slide copy and the educational picture editor.

THE GUARD AGAINST MUSH
    A model distilling "taste" drifts toward generic calm-natural-soft
    language within weeks. So every principle must carry a VERBATIM QUOTE
    from feedback.md or references.md and name where it came from. The code
    checks the quote really appears in the source text; an uncited or
    misquoted principle is DROPPED, not kept. Outcomes may support a
    principle but cannot be its only source — the audience's numbers are
    evidence, Marcus's words are the taste.

VERSIONED, SO HE CAN AUDIT IT
    brief.md carries a version (date.vN) and a changelog of what changed and
    why. Marcus reads it; if a line is wrong he says so in the Taste Notes
    tab and the next distill has that as input.

CADENCE
    Weekly, Monday, BEFORE screening (screen_runner calls maybe_distill), and
    a stamp-guarded check on the reel tick so a missed Monday still catches
    up. `python3 taste_brief.py --distill` forces one. A distill with no new
    input since the last one is skipped.

FAIL-OPEN
    brief_block() is what writers call. It reads a LOCAL CACHE
    (_state/taste-brief.md) refreshed on every distill and on every
    taste_store sync. Cache missing -> a one-line placeholder; the brand guide
    governs. Nothing here can stop a run.

THE RULE
    The brief changes HOW things are written. It never decides WHETHER.

CHANGELOG
    1.2  2026-09-16  After the second live distill: the block trimmed at 2000
                     chars and dropped principle 8, so the cap is 3200 and the
                     reference label is shorter ("ref IMG_x.jpg:"). A stage
                     with a brief but no applicable lines now says so instead
                     of "no brief yet".
    1.1  2026-09-16  LANE ROUTING, after the first live distill. All eight
                     principles were visual (from reference-image notes) and
                     were handed to the reel caption and educational copy
                     writers as if they were voice guidance. Now: a principle
                     sourced from a reference image is tagged "visual" and
                     reaches only the stages that choose or make pictures;
                     brief_block(stage) filters by stage. Also labels
                     reference-derived quotes as the vision note's words about
                     an image Marcus chose, not his own sentence.
    1.0  2026-09-16  First build (taste layer step 3).
=============================================================================
"""

import json
import os
import re
import shutil
import tempfile
import time
from datetime import datetime

import config
import reel_config

VERSION = "1.0"
CACHE_PATH = os.path.join(reel_config.BASE_DIR, "_state", "taste-brief.md")
STAMP_PATH = os.path.join(reel_config.BASE_DIR, "_state", "taste-brief.stamp")
DISTILL_EVERY_DAYS = getattr(config, "TASTE_DISTILL_EVERY_DAYS", 6)
MAX_PRINCIPLES = getattr(config, "TASTE_BRIEF_MAX_PRINCIPLES", 10)
MAX_BLOCK_CHARS = getattr(config, "TASTE_BRIEF_MAX_CHARS", 3200)
MIN_SOURCE_CHARS = 40          # nothing to distill below this

SCHEMA = {
    "principles": {"type": "list", "required": True},
    "changes":    {"type": "str", "required": False},
}

# Which principles each writer receives. A principle's `lanes` is one of
# all · images · educational · reels · visual (auto-assigned when the only
# source is a reference image). Copy writers never see "visual".
STAGE_LANES = {
    "image-prompts": {"all", "images", "visual"},
    "screening":     {"all", "images", "visual"},
    "caption":       {"all", "images"},
    "reel-hook":     {"all", "reels"},
    "reel-caption":  {"all", "reels"},
    "writer_edu":    {"all", "educational"},
    "caption_edu":   {"all", "educational"},
    "picker_edu":    {"all", "educational", "visual"},
}
REFERENCE_SOURCE = re.compile(r"\.(jpe?g|png|webp)\b", re.I)

PLACEHOLDER = ("(No taste brief yet. The brand guide governs; Marcus's notes "
               "will appear here once distilled.)")
NONE_FOR_STAGE = ("(Nothing in the taste brief applies to this stage yet — so far "
                  "it is visual. The brand guide governs.)")


def log(msg):
    print(f"[taste_brief] {msg}", flush=True)


# ── the guard ───────────────────────────────────────────────────────────────

def _norm(s):
    s = (s or "").lower()
    s = s.replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip()


def validate_principles(principles, sources_text):
    """Keep only principles whose quote really appears in the sources.
    Returns (kept, dropped_reasons)."""
    src = _norm(sources_text)
    kept, dropped = [], []
    for p in principles or []:
        if not isinstance(p, dict):
            dropped.append("not an object")
            continue
        text = (p.get("text") or "").strip()
        quote = (p.get("quote") or "").strip().strip('"').strip()
        source = (p.get("source") or "").strip()
        if not text:
            dropped.append("empty text")
            continue
        if len(quote) < 6:
            dropped.append(f"no quote: {text[:50]}")
            continue
        if _norm(quote) not in src:
            dropped.append(f"quote not in sources: \"{quote[:50]}\"")
            continue
        if not source:
            dropped.append(f"no source: {text[:50]}")
            continue
        lanes = (p.get("lanes") or "all").strip().lower() or "all"
        # A principle whose only evidence is a reference image is about how
        # pictures look. It must not reach a copy writer as voice guidance.
        if REFERENCE_SOURCE.search(source) and lanes in ("all", "images", "educational"):
            lanes = "visual"
        kept.append({"text": text, "quote": quote, "source": source,
                     "lanes": lanes})
        if len(kept) >= MAX_PRINCIPLES:
            break
    return kept, dropped


# ── files ───────────────────────────────────────────────────────────────────

def _read(path):
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return ""


def _next_version(previous_md):
    today = datetime.now().strftime("%Y-%m-%d")
    m = re.search(r"VERSION:\s*(\d{4}-\d{2}-\d{2})\.v(\d+)", previous_md or "")
    if m and m.group(1) == today:
        return f"{today}.v{int(m.group(2)) + 1}"
    return f"{today}.v1"


def _previous_changelog(previous_md):
    m = re.search(r"## Changelog\n(.*)$", previous_md or "", re.S)
    return m.group(1).strip() if m else ""


def render(principles, version, changes, previous_md, n_sources):
    lines = [f"<!-- VERSION: {version} -->",
             "# What Marcus wants — the taste brief",
             f"Distilled {datetime.now():%Y-%m-%d %H:%M} by taste_brief.py {VERSION} "
             f"from taste/feedback.md, references.md and outcomes.md "
             f"({n_sources} source item(s)). Every line quotes Marcus or the "
             f"team and names where it came from; anything uncited was dropped. "
             f"To correct a line, write in the Taste Notes tab.",
             ""]
    if not principles:
        lines.append("(Nothing distillable yet — too little feedback. The brand guide governs.)")
    for i, p in enumerate(principles, 1):
        lane = f" [{p['lanes']}]" if p.get("lanes") and p["lanes"] != "all" else ""
        lines.append(f"{i}. {p['text']}{lane}")
        if REFERENCE_SOURCE.search(p['source']):
            lines.append(f"   — ref {p['source']}: \"{p['quote']}\"")
        else:
            lines.append(f"   — \"{p['quote']}\" ({p['source']})")
    lines += ["", "## Changelog",
              f"- {version}: {changes or 'first distill'}"]
    prev = _previous_changelog(previous_md)
    if prev:
        lines.append(prev)
    return "\n".join(lines) + "\n"


def block_from_md(md, stage=None):
    """The part writers get: the numbered principles only, filtered to the
    stage's lanes, renumbered, bounded."""
    if not md:
        return PLACEHOLDER
    body = md.split("## Changelog")[0]
    body = re.sub(r"<!--.*?-->\n?", "", body, flags=re.S)
    allowed = STAGE_LANES.get(stage) if stage else None
    out, n, keep = [], 0, True
    for l in body.split("\n"):
        m = re.match(r"^\s*\d+\.\s+(.*?)(?:\s+\[([a-z, ]+)\])?\s*$", l)
        if m:
            lanes = {x.strip() for x in (m.group(2) or "all").split(",")}
            keep = allowed is None or bool(lanes & allowed)
            if keep:
                n += 1
                tag = f" [{m.group(2)}]" if m.group(2) else ""
                out.append(f"{n}. {m.group(1)}{tag}")
            continue
        if re.match(r"^\s*(—|\()", l) and keep:
            out.append(l)
    text = "\n".join(out).strip()
    if not text:
        return NONE_FOR_STAGE if re.search(r"^\s*\d+\.", body, re.M) else PLACEHOLDER
    if len(text) > MAX_BLOCK_CHARS:
        text = text[:MAX_BLOCK_CHARS].rsplit("\n", 1)[0] + "\n(brief trimmed)"
    return text


def brief_block(stage=None):
    """What every writer calls, with its stage name so it gets only the
    principles that apply to it. Never raises."""
    try:
        return block_from_md(_read(CACHE_PATH), stage)
    except Exception:
        return PLACEHOLDER


def refresh_cache_from(mem_dir):
    """Copy taste/brief.md from a memory clone into the local cache.
    Called by taste_store.sync so lanes see a brief distilled elsewhere."""
    try:
        src = os.path.join(mem_dir, "taste", "brief.md")
        if os.path.exists(src):
            os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
            shutil.copyfile(src, CACHE_PATH)
            return True
    except Exception as e:
        log(f"cache refresh failed ({type(e).__name__})")
    return False


# ── the distill ─────────────────────────────────────────────────────────────

def _fingerprint(mem_dir):
    import hashlib
    h = hashlib.sha1()
    for name in ("feedback.md", "references.md", "outcomes.md"):
        h.update(_read(os.path.join(mem_dir, "taste", name)).encode())
    return h.hexdigest()[:12]


def distill(force=False):
    """Clone, distill, validate, write brief.md, push. Never raises.
    Returns (ok, message)."""
    workdir = tempfile.mkdtemp(prefix="selene_brief_")
    try:
        from caption_runner import clone_memory
        import pipeline_state
        from claude_client import invoke_claude_json, load_prompt
        mem = clone_memory(workdir)
        if not mem:
            return False, "memory repo clone failed"
        tdir = os.path.join(mem, "taste")
        feedback = _read(os.path.join(tdir, "feedback.md"))
        references = _read(os.path.join(tdir, "references.md"))
        outcomes = _read(os.path.join(tdir, "outcomes.md"))
        previous = _read(os.path.join(tdir, "brief.md"))
        sources = feedback + "\n" + references
        if len(_norm(sources)) < MIN_SOURCE_CHARS:
            return False, "nothing to distill yet (no feedback or references)"

        fp = _fingerprint(mem)
        if not force and previous and f"sources:{fp}" in previous:
            _stamp()
            return True, "no new input since the last distill — skipped"

        template, pv = load_prompt("taste-brief")
        out_path = os.path.join(workdir, "brief.json")
        prompt = template.format(
            feedback=feedback[:12000], references=references[:8000],
            outcomes=outcomes[:6000], previous=previous[:4000] or "(none yet)",
            max_principles=MAX_PRINCIPLES, out_path=out_path)
        ok, result = invoke_claude_json(
            prompt, workdir, out_path, schema=SCHEMA, stage="taste_brief",
            timeout=600)
        if not ok:
            return False, f"distill call failed: {str(result)[:120]}"

        kept, dropped = validate_principles(result.get("principles"), sources)
        for d in dropped:
            log(f"  dropped: {d}")
        version = _next_version(previous)
        changes = (result.get("changes") or "").strip() or "first distill"
        if dropped:
            changes += f" ({len(dropped)} uncited line(s) dropped by the guard)"
        md = render(kept, version, changes, previous,
                    n_sources=sources.count("\n- "))
        md = md.replace("-->\n", f"-->\n<!-- sources:{fp} -->\n", 1)
        os.makedirs(tdir, exist_ok=True)
        with open(os.path.join(tdir, "brief.md"), "w") as f:
            f.write(md)
        refresh_cache_from(mem)
        pushed, msg = pipeline_state.push_with_retry(
            mem, f"Taste brief {version}", logger=log)
        _stamp()
        return pushed, (f"brief {version}: {len(kept)} principle(s), "
                        f"{len(dropped)} dropped — {msg}")
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:120]}"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _stamp():
    try:
        os.makedirs(os.path.dirname(STAMP_PATH), exist_ok=True)
        with open(STAMP_PATH, "w") as f:
            f.write(datetime.now().isoformat(timespec="minutes"))
    except Exception:
        pass


def due():
    try:
        return time.time() - os.path.getmtime(STAMP_PATH) >= DISTILL_EVERY_DAYS * 86400
    except Exception:
        return True


def maybe_distill():
    """Weekly, stamp-guarded. Called before Monday screening and on the reel
    tick. Never raises."""
    if not due():
        return False, "not due"
    ok, msg = distill()
    log(f"distill: {msg}" if ok else f"WARNING: distill failed ({msg})")
    return ok, msg


if __name__ == "__main__":
    import sys
    if "--distill" in sys.argv:
        ok, msg = distill(force="--force" in sys.argv)
        print(("ok: " if ok else "FAILED: ") + msg)
    for stage in STAGE_LANES:
        print(f"\n--- {stage} receives ---\n{brief_block(stage)}")
    print()
