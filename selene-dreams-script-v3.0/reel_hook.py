"""
reel_hook.py — write one hook, in a rotating pattern, for a trial reel
=============================================================================
VERSION 1.4 — 2026-09-16

WHAT A HOOK IS HERE
    The variable under test. Everything else about a trial reel is held as
    constant as we can manage; the hook is what changes between runs of the
    same source video, so that run-over-run differences mean something.

TWO APPLICATION MODES
    caption  — the hook becomes the caption's first line. Video untouched.
    overlay  — the hook is burned into the opening seconds.

    DEFAULT IS caption, on evidence gathered 2026-09-09: four top-engagement
    bedding reels were opened and inspected (Brooklinen x3, Parachute x1) and
    NONE of them burns a text hook onto the video. The category's hook lives in
    the caption's first line and the opening visual.

    overlay stays available because it is the interesting experiment: it is
    worth testing precisely because the category does not do it. HOOK_ROTATE
    alternates the two so they can be compared at all.

PATTERNS, NOT LINES
    The bank stores STRUCTURES with provenance and evidence strength. Copying a
    competitor's line would be both derivative and legally careless; the writer
    is told to rewrite anything that reads like one.

CHANGELOG
    1.4  2026-09-16  {taste_brief}: the cross-lane distilled brief joins the
                     lane's own feedback block. Fail-open.
    1.3  2026-09-16  FEEDBACK. The prompt now carries Marcus's notes and
                     ratings on earlier reels ({taste}, via reel_feedback),
                     and choose_pattern() drops a pattern he has rated badly
                     from the ROTATION. Nothing here can park a video —
                     feedback changes what is written, not whether.
    1.2  2026-09-10  BRAND GROUNDING + VERIFIED CLAIMS. Marcus read "This gauze
                     likes to make an entrance" over footage of a woman wrapping
                     herself in a blanket and identified the real gap: the hook
                     writer knew the footage and the pattern but nothing about
                     what Selene is FOR, so it wrote about a fabric performing
                     instead of about rest. The prompt now carries the mission's
                     grounding/escape duality and the WE ARE / WE ARE NOT lists,
                     and the writer must self-flag connects_to_rest — false
                     parks the video, exactly like truthful.
                     Also loads claims_edu.md, so a hook can no longer invent a
                     material, weave or thermal claim. WE-ARE-NOT words are
                     rejected outright.
    1.1  2026-09-09  write_hook() accepts an explicit mode. The control tab now
                     decides overlay per video (no on-screen text -> overlay),
                     so the rotation is only a fallback when nothing decides.
    1.0  2026-09-09  First build.
=============================================================================
"""

import os
import re

import reel_config
from claude_client import invoke_claude_json, load_prompt

HOOK_SCHEMA = {
    "hook":              {"type": "str"},
    "pattern":           {"type": "str"},
    "why":               {"type": "str", "required": False},
    "truthful":          {"type": "bool"},
    "connects_to_rest":  {"type": "bool"},
}


def load_claims():
    """The verified product facts, or a hard refusal line if unreadable.

    Never raises: if the file is missing the writer is told it may state NO
    product facts at all, which is the safe direction to fail in.
    """
    try:
        with open(reel_config.CLAIMS_PATH) as fh:
            return fh.read().strip()
    except Exception as e:
        log(f"  WARNING: verified claims file unreadable ({e}) — "
            f"the hook may state NO product facts this run")
        return ("(The verified claims file could not be read. You may state NO "
                "product facts at all: no materials, weaves, specs, "
                "certifications or colourways.)")

# Structures, with the evidence behind each. Mirrors hook-bank-v1.0.md; that
# file is the human-readable authority and carries the full provenance.
PATTERNS = [
    {
        "id": "H2",
        "name": "Object, stated plainly",
        "gist": "name what is on screen in the flattest possible language, then stop",
        "strength": "STRONG",
        "detail": (
            "Trust the footage completely. No adjective doing persuasive work.\n"
            "The restraint IS the voice. Six to ten words. This is the closest\n"
            "match to Selene's register and the safest default.\n"
            "Evidence: Parachute's 19.1%-engagement reel is pure product footage\n"
            "with no text at all; Piglet in Bed's one-liner drew 2,695 likes\n"
            "against 311 for their full product explainer."),
        "needs_people": False,
    },
    {
        "id": "H3",
        "name": "Colour or material as subject",
        "gist": "let a colour or fabric name carry the line, addressed almost as a person",
        "strength": "MEDIUM",
        "detail": (
            "The material is the subject of the sentence, not an attribute of\n"
            "the product. Works when the footage is genuinely about a colour or\n"
            "a weave. Do not use it on footage where the colour is incidental.\n"
            "Evidence: Quince's colour-led line ran above that account's median,\n"
            "though their view counts look amplified."),
        "needs_people": False,
    },
    {
        "id": "H5",
        "name": "Quiet contradiction",
        "gist": "set an expectation in a few words, then undercut it",
        "strength": "WEAK",
        "detail": (
            "Two beats. The turn must be gentle, not a gotcha. Selene is not a\n"
            "brand that shouts, so the contradiction should feel observed rather\n"
            "than engineered.\n"
            "Evidence: structural inference only. UNTESTED for Selene, which is\n"
            "exactly why it is in the rotation."),
        "needs_people": False,
    },
    {
        "id": "H1",
        "name": "Named person, two beats",
        "gist": "a named person, a short declarative, then a flat product line",
        "strength": "STRONG",
        "detail": (
            "The humour sits in the gap between setup and anticlimax.\n"
            "Evidence: Brooklinen, 4 of 4 instances in the top engagement band.\n"
            "ONLY usable when the footage genuinely shows a real person. Never\n"
            "invent a customer and present them as real."),
        "needs_people": True,
    },
]

MODE_RULES = {
    "caption": (
        "This hook becomes the FIRST LINE OF THE CAPTION. The video is not\n"
        "modified. It has to work as readable prose that the rest of the caption\n"
        "can continue from, so it must end cleanly. This is the mode the\n"
        "category actually uses."),
    "overlay": (
        "This hook will be BURNED INTO THE VIDEO over its opening seconds.\n"
        "So: short. Under about 45 characters if you can. It is read at a glance\n"
        "on a small screen, often muted, by someone already scrolling. No\n"
        "punctuation that needs parsing. It must stand completely alone."),
}


def log(msg):
    print(f"[reel_hook] {msg}", flush=True)


def choose_pattern(description, used_pattern_ids=(), avoid=()):
    """Rotation, never random. Filters by what the footage can support.

    avoid: pattern ids Marcus has rated badly (reel_feedback). They leave the
    rotation but never block a run: if avoiding them leaves nothing, they
    come back.
    """
    used = list(used_pattern_ids)
    eligible = [p for p in PATTERNS
                if not p["needs_people"] or description.get("has_people")]
    if not eligible:
        eligible = [p for p in PATTERNS if not p["needs_people"]]
    if avoid:
        kept = [p for p in eligible if p["id"] not in avoid]
        if kept:
            log(f"  patterns rated low by Marcus, out of rotation: "
                f"{', '.join(a for a in avoid if a in {p['id'] for p in eligible})}")
            eligible = kept

    fresh = [p for p in eligible if p["id"] not in used]
    pool = fresh or eligible

    def last_used(p):
        try:
            return used[::-1].index(p["id"])
        except ValueError:
            return len(used) + 1
    pool.sort(key=lambda p: (-last_used(p), PATTERNS.index(p)))
    chosen = pool[0]
    log(f"  pattern: {chosen['id']} {chosen['name']} ({chosen['strength']})")
    return chosen


def choose_mode(variant_index):
    if not reel_config.HOOK_ROTATE:
        return reel_config.HOOK_MODE
    rot = reel_config.HOOK_MODE_ROTATION
    return rot[variant_index % len(rot)]


def _taste_brief(stage="reel-hook"):
    try:
        import taste_brief
        return taste_brief.brief_block(stage)
    except Exception:
        return "(taste brief unavailable this run)"


def _feedback(state):
    """(taste block, low-rated pattern ids). Never raises."""
    try:
        import reel_feedback
        st = state if state is not None else {}
        return (reel_feedback.taste_block(st, "hook"),
                reel_feedback.low_rated_patterns(st))
    except Exception as e:
        log(f"  feedback unavailable ({type(e).__name__}) — writing without it")
        return "(feedback unavailable this run)", []


def write_hook(description, work_dir, variant_index, used=(), attempts=2,
               mode=None, state=None):
    """Returns (hook_text, meta). Raises if no honest hook could be written."""
    os.makedirs(work_dir, exist_ok=True)
    used_ids = [u["pattern_id"] for u in used if u.get("pattern_id")]
    taste, avoid = _feedback(state)
    pattern = choose_pattern(description, used_ids, avoid=avoid)
    mode = mode or choose_mode(variant_index)
    log(f"  mode: {mode} (variant {variant_index + 1})")

    out_path = os.path.join(work_dir, f"hook_{variant_index + 1}.json")
    template, version = load_prompt("reel-hook")

    used_lines = ("\n".join(f'  - "{u["hook"]}" ({u.get("pattern_id", "?")})'
                            for u in used)
                  or "  (none — this is the first hook for this video)")

    prompt = template.format(
        summary=description.get("summary", ""),
        on_screen=description.get("on_screen", ""),
        product_guess=description.get("product_guess", "unclear"),
        fabric_guess=description.get("fabric_guess", "unclear"),
        mood=description.get("mood", ""),
        hook_moment=description.get("hook", ""),
        has_text_overlay=("yes" if description.get("has_text_overlay") else "no"),
        has_people=("yes" if description.get("has_people") else "no"),
        mode=mode,
        mode_rule=MODE_RULES[mode],
        pattern_name=pattern["name"],
        pattern_gist=pattern["gist"],
        pattern_strength=pattern["strength"],
        pattern_detail=pattern["detail"],
        used_hooks=used_lines,
        claims=load_claims(),
        taste=taste,
        taste_brief=_taste_brief(),
        out_path=out_path,
    )

    last = ""
    for attempt in range(1, attempts + 1):
        ok, result = invoke_claude_json(
            prompt, work_dir, out_path,
            schema=HOOK_SCHEMA, stage="caption", timeout=300)
        if not ok:
            last = str(result)
            continue

        hook = result["hook"].strip()
        valid, why = validate_hook(hook, mode, result)
        if valid:
            log(f'  hook: "{hook}"')
            return hook, {
                "pattern_id": pattern["id"],
                "pattern_name": pattern["name"],
                "pattern_strength": pattern["strength"],
                "mode": mode,
                "why": result.get("why", ""),
                "prompt_version": version,
            }
        last = why
        log(f"  hook REJECTED: {why}")
        prompt = (f"{prompt}\n\n---\nYOUR PREVIOUS HOOK WAS REJECTED: {why}.\n"
                  f"Write the corrected JSON to {out_path} again, same pattern "
                  f"and mode. Fix only the stated problem.")

    raise ValueError(f"no usable hook after {attempts} attempts: {last}")


BANNED = ("indulge", "elevate", "elevated", "luxurious", "dive into", "unlock",
          "consider this your sign", "treat yourself")

# Numbers in a hook are a claim, and several of Selene's public claims are
# under audit (340TC not 400, GOTS unconfirmed, 365-day not night). A hook is
# the worst place to put a number we might have to retract.
NUMERIC = re.compile(r"\d")


# The deck's WE ARE NOT list. A hook containing one of these is off-brand by
# the brand's own definition, so this is a rule rather than a judgement call.
OFF_BRAND = ("rough", "restrictive", "mechanical", "artificial", "industrial",
             "harsh", "coarse", "flimsy", "uninviting")


def validate_hook(hook, mode, result=None):
    """Return (ok, message). Never raises."""
    if result is not None and result.get("truthful") is False:
        return False, ("the writer flagged it could not write an honest hook "
                       "for this footage")
    if result is not None and result.get("connects_to_rest") is False:
        return False, ("the writer flagged the hook does not reach the "
                       "territory of rest — it is about an object, not a moment")
    if not hook:
        return False, "empty hook"
    if "—" in hook or "–" in hook:
        return False, "contains an em or en dash"
    if "?" in hook:
        return False, "asks a question (Selene does not reply to comments)"
    if NUMERIC.search(hook):
        return False, "contains a number, which reads as an unverified claim"
    low = hook.lower()
    for b in BANNED:
        if b in low:
            return False, f"uses banned phrase '{b}'"
    for w in OFF_BRAND:
        if re.search(rf"\b{w}\b", low):
            return False, f"uses '{w}', which is on the brand's WE ARE NOT list"
    if hook != hook.strip():
        return False, "has leading or trailing whitespace"
    if hook.isupper():
        return False, "is all caps"

    words = len(hook.split())
    if mode == "overlay":
        if len(hook) > 60:
            return False, f"{len(hook)} chars is too long to read at a glance (max 60)"
        if words > 12:
            return False, f"{words} words is too many for an overlay (max 12)"
    else:
        if words > 20:
            return False, f"{words} words is too long for a caption opener (max 20)"
    return True, "ok"
