"""
taste_brief.py — distill the taste layer into ONE brief every writer reads
=============================================================================
VERSION 1.6 — 2026-09-30

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
    misquoted principle is DROPPED, not kept.

PERFORMANCE CAN TEACH (1.3)
    Marcus's goal metric (2026-09-23): reach + shares + saves. perf_score()
    = reach + PERF_WEIGHT x (shares + saves). build_performance() ranks each
    lane's posts (7d window when enough exist) and hands the distill the TOP
    and BOTTOM few, each with an id (P1..), what the post showed and its
    numbers. A principle may now be sourced from PERFORMANCE alone, but the
    guard requires its quote to be verbatim from a PERFORMANCE line and its
    source to cite at least TWO post ids — one lucky post is not a pattern.
    Order of authority: Marcus's feedback > performance > reference notes.

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
    1.6  2026-09-30  FINGERPRINT IGNORES THE "Generated" STAMP. _fingerprint
                     hashed feedback/references/outcomes.md whole, so the
                     taste_store timestamp made every distill look like new
                     input and the "no new input — skipped" path never fired.
                     Companion to taste_store 1.6.
    1.5  2026-09-30  "research" STAGE. The weekly research phase 4 now
                     receives the brief too (research lane v2.1); it sees
                     the same lanes as screening (all/images/visual) since
                     it chooses references for the image lane. No other
                     change.
    1.4  2026-09-28  LANES FOR PERFORMANCE PRINCIPLES + A PERFORMANCE BLOCK
                     FOR WRITERS. (a) The first performance principle (direct-
                     address captions) reached writer_edu — slide copy is not a
                     caption. A performance-sourced principle now gets its lane
                     from what it says: "visual" (pictures) or "copy" (captions
                     and hooks); "all" is rewritten to "copy". New lane "copy"
                     reaches caption, reel-hook, reel-caption and caption_edu —
                     never writer_edu, picker_edu, image-prompts or screening.
                     (b) performance_block(lane): the ranked top/bottom posts
                     of ONE lane, with product + scene, from the local cache
                     taste_store writes (_state/taste-outcomes.json). The image
                     prompt writer and the screener now see what the audience
                     rewarded, not only their own QA scores. Fail-open.
    1.3  2026-09-23  Performance may source principles (see above). Before
                     this, 53 posts' reach/shares/saves could never become a
                     principle because outcomes needed a paired rating, which
                     almost never exists — the loop had no audience signal.
                     Adds perf_score, build_performance, {performance} in the
                     prompt (taste-brief v3), the two-post guard in
                     validate_principles. Also fixed VERSION constant (had
                     stayed "1.0" through 1.1 and 1.2).
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

VERSION = "1.6"
CACHE_PATH = os.path.join(reel_config.BASE_DIR, "_state", "taste-brief.md")
STAMP_PATH = os.path.join(reel_config.BASE_DIR, "_state", "taste-brief.stamp")
DISTILL_EVERY_DAYS = getattr(config, "TASTE_DISTILL_EVERY_DAYS", 6)
MAX_PRINCIPLES = getattr(config, "TASTE_BRIEF_MAX_PRINCIPLES", 10)
MAX_BLOCK_CHARS = getattr(config, "TASTE_BRIEF_MAX_CHARS", 3200)
MIN_SOURCE_CHARS = 40          # nothing to distill below this
PERF_WEIGHT = getattr(config, "TASTE_PERF_WEIGHT", 25)        # 1 share/save ~ 25 reached accounts
PERF_MIN_POSTS = getattr(config, "TASTE_PERF_MIN_POSTS", 6)   # per lane, before ranking means anything
PERF_TOP_N = getattr(config, "TASTE_PERF_TOP_N", 3)           # top N and bottom N per lane
PERF_ID = re.compile(r"\bP(\d+)\b")

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
    "research":      {"all", "images", "visual"},
    "caption":       {"all", "images", "copy"},
    "reel-hook":     {"all", "reels", "copy"},
    "reel-caption":  {"all", "reels", "copy"},
    "writer_edu":    {"all", "educational"},
    "caption_edu":   {"all", "educational", "copy"},
    "picker_edu":    {"all", "educational", "visual"},
}
# Which outcome lanes feed each writer's performance block.
PERF_LANES = {
    "image-prompts": ("images",),
    "screening":     ("images",),
    "caption":       ("images",),
    "reel-hook":     ("reels", "manual"),
    "reel-caption":  ("reels", "manual"),
    "picker_edu":    ("educational",),
    "caption_edu":   ("educational",),
}
OUTCOMES_CACHE = os.path.join(reel_config.BASE_DIR, "_state", "taste-outcomes.json")
NO_PERF = "(No measured posts for this lane yet — nothing to rank.)"
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


def perf_score(r):
    """Marcus's goal metric: reach + PERF_WEIGHT x (shares + saves).
    None when reach is unknown."""
    try:
        reach = r.get("reach")
        if reach in (None, ""):
            return None
        sends = (r.get("shares") or 0) + (r.get("saves") or r.get("saved") or 0)
        return int(reach) + PERF_WEIGHT * int(sends)
    except Exception:
        return None


def build_performance(rows):
    """Top and bottom posts per lane, each with an id. Deterministic: the
    ranking is done here, not by the model. Returns '' when no lane has
    enough posts."""
    by_lane = {}
    for r in rows or []:
        sc = perf_score(r)
        if sc is None:
            continue
        by_lane.setdefault(r.get("lane") or "?", []).append(dict(r, score=sc))
    out, pid = [], 0
    for lane in sorted(by_lane):
        posts = by_lane[lane]
        wk = [p for p in posts if p.get("window") == "7d"]
        if len(wk) >= PERF_MIN_POSTS:
            posts, win = wk, "7d"
        else:
            win = "mixed 72h/7d"
        if len(posts) < PERF_MIN_POSTS:
            continue
        posts.sort(key=lambda p: p["score"], reverse=True)
        n = min(PERF_TOP_N, len(posts) // 2)
        med = posts[len(posts) // 2]["score"]
        out.append(f"#### {lane} — {len(posts)} posts ranked ({win}), median score {med}")
        out.append(f"(each line: id · TOP/BOTTOM · [{lane}] · what the post showed · format · numbers)")
        for label, group in (("TOP", posts[:n]), ("BOTTOM", posts[-n:])):
            for p in group:
                pid += 1
                what = " ".join(str(p.get("what") or "").split())[:320]
                out.append(
                    f"- P{pid} {label} · [{lane}] · {what} · {p.get('choices') or ''} · "
                    f"reach {p.get('reach')}, shares {p.get('shares') or 0}, "
                    f"saves {p.get('saves') or 0}, score {p['score']} · {p.get('posted', '')}")
        out.append("")
    return "\n".join(out).strip()


def performance_block(stage):
    """What a writer gets: its own lanes' ranked posts from the local cache.
    Never raises; a placeholder when there is nothing."""
    try:
        lanes = PERF_LANES.get(stage)
        if not lanes:
            return NO_PERF
        rows = json.loads(_read(OUTCOMES_CACHE) or "[]")
        rows = [r for r in rows if (r.get("lane") or "") in lanes]
        text = build_performance(rows)
        if not text:
            return NO_PERF
        if len(text) > MAX_BLOCK_CHARS:
            text = text[:MAX_BLOCK_CHARS].rsplit("\n", 1)[0] + "\n(trimmed)"
        return text
    except Exception:
        return NO_PERF


def validate_principles(principles, sources_text, perf_text=""):
    """Keep only principles whose quote really appears in the sources.
    A quote found only in the PERFORMANCE block must cite >= 2 post ids.
    Returns (kept, dropped_reasons)."""
    src = _norm(sources_text)
    perf = _norm(perf_text)
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
        in_src = _norm(quote) in src
        in_perf = bool(perf) and _norm(quote) in perf
        if not (in_src or in_perf):
            dropped.append(f"quote not in sources: \"{quote[:50]}\"")
            continue
        if in_perf and not in_src and len(set(PERF_ID.findall(source))) < 2:
            dropped.append(f"performance principle cites < 2 posts: {text[:50]}")
            continue
        # A performance principle is about published posts: what they showed
        # ("visual") or what they said ("copy"). It is never voice guidance for
        # slide copy or a picker, so "all" is rewritten to "copy".
        perf_only = in_perf and not in_src
        if perf_only and (p.get("lanes") or "all").strip().lower() in ("all", ""):
            p = dict(p, lanes="copy")
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
             f"({n_sources} source item(s)). Every line quotes Marcus, the "
             f"team, or the measured performance of 2+ posts (P ids) and names "
             f"where it came from; anything uncited was dropped. "
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
        body = "\n".join(l for l in _read(os.path.join(mem_dir, "taste", name)).splitlines()
                         if not l.startswith("Generated "))       # 1.6: stamp is not input
        h.update(body.encode())
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
        try:
            performance = build_performance(
                json.loads(_read(os.path.join(tdir, "outcomes.json")) or "[]"))
        except Exception as e:
            log(f"performance unavailable ({type(e).__name__})")
            performance = ""
        references = _read(os.path.join(tdir, "references.md"))
        outcomes = _read(os.path.join(tdir, "outcomes.md"))
        previous = _read(os.path.join(tdir, "brief.md"))
        sources = feedback + "\n" + references
        if len(_norm(sources + performance)) < MIN_SOURCE_CHARS:
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
            performance=performance[:6000] or "(no lane has enough measured posts yet)",
            max_principles=MAX_PRINCIPLES, out_path=out_path)
        ok, result = invoke_claude_json(
            prompt, workdir, out_path, schema=SCHEMA, stage="taste_brief",
            timeout=600)
        if not ok:
            return False, f"distill call failed: {str(result)[:120]}"

        kept, dropped = validate_principles(result.get("principles"), sources,
                                            performance)
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
