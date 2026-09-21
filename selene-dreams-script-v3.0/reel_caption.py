"""
reel_caption.py — caption a trial reel, in the reel routing
=============================================================================
VERSION 1.6 — 2026-09-16

THE DECISION THIS IMPLEMENTS
    On 2026-09-07 the seven-style caption register shipped with reels marked
    DEFERRED in Stage 0, and Marcus asked to be prompted when the reel flow
    was actually built. This is that prompt, answered:

      Eligible for reels:  One Line · Two Beat · Meet the Product
      Excluded:            The Detail · Three Beats · Care Note
                           (explaining styles assume a reader who already
                            cares; a trial reel reaches only strangers)
      Excluded:            Current Style (sale/promo and The Selene Story
                            only, and a trial reel is neither)

    Reels therefore no longer fall through to the image-lane defaults, which
    is the failure the deferral existed to prevent.

WHAT IT REUSES RATHER THAN FORKS
    validate_caption(), read_recent_styles() and append_caption_log() are
    imported from caption_runner, not copied. Forking the validator is how the
    5-line format ended up gated in three places; that is not repeated here.

CHANGELOG
    1.6  2026-09-16  {taste_brief}: the cross-lane distilled brief. Fail-open.
    1.5  2026-09-16  FEEDBACK. write_caption() takes state and passes
                     Marcus's notes/ratings on earlier reels into the prompt
                     as {taste}. Context only: it cannot change the style
                     rotation or park a video.
    1.4  2026-09-10  Passes the verified claims file and carries the brand
                     territory. The caption stage is where unverified product
                     facts actually appeared in production, so this matters
                     more here than in the hook.
    1.3  2026-09-09  A product CONFIRMED from the filename (reel_products) is
                     never "unclear", so "Meet the Product" and product
                     hashtags come back. Marcus naming the product beats a
                     model looking at six frames.
    1.2  2026-09-09  "UNCLEAR PRODUCT" NOW PROPAGATES. First real dry run
                     exposed three linked bugs with one root cause: the vision
                     pass honestly reported product_guess "unclear", and
                     NOTHING downstream listened.
                       (a) "Meet the Product" was still chosen — the one style
                           whose entire job is to name the product plainly. It
                           is now INELIGIBLE when the product is unclear.
                       (b) the caption's hashtags asserted "#linenthrow", a
                           product claim the vision pass had explicitly refused
                           to make. PRODUCT NOUNS IN HASHTAGS ARE NOW REJECTED
                           when the product is unclear.
                     Numbers were already blocked in hooks; this closes the same
                     hole for product claims, which is the more likely one.
    1.1  2026-09-09  HOOK AWARE. write_caption() takes the hook and its mode.
                     In caption mode the caption MUST open with the hook line
                     verbatim, and that is verified after generation, not
                     merely requested — a hook that the caption quietly
                     reworded would destroy the comparison the whole lane
                     exists to make. In overlay mode the caption must not
                     repeat what is already burned into the video.
    1.0  2026-09-09  First build.
=============================================================================
"""

import os

import reel_config
from claude_client import invoke_claude_json, load_prompt
from caption_runner import (validate_caption, read_recent_styles,
                            append_caption_log)

CAPTION_SCHEMA = {
    "style":            {"type": "str", "choices": reel_config.REEL_ELIGIBLE_STYLES},
    "caption":          {"type": "str"},
    "seo_phrase_used":  {"type": "str", "required": False},
    "reasoning":        {"type": "str", "required": False},
}

STYLE_SPECS = {
    "One Line": (
        "ONE sentence. Maximum 14 words. No second paragraph. It should be the\n"
        "kind of line someone screenshots, not a summary of the product. This is\n"
        "the strongest style for a cold scroll and the hardest to write: if the\n"
        "line is not genuinely good, use the rotation's next option rather than\n"
        "padding this one out."),
    "Two Beat": (
        "ONE paragraph, two movements. The first beat sets something down; the\n"
        "second turns it, deepens it, or admits something. No separator lines.\n"
        "This is the workhorse. Two or three sentences total."),
    "Meet the Product": (
        "ONE paragraph, up to three sentences, that names the product plainly\n"
        "and gives the single most concrete reason it exists. For a stranger\n"
        "this is often the most useful caption on the account. Say the product\n"
        "name once. Do not stack benefits after it."),
}


def log(msg):
    print(f"[reel_caption] {msg}", flush=True)


def product_is_unclear(description):
    """True when nobody has committed to a product.

    Marcus declaring it in the filename is GROUND TRUTH and outranks the vision
    pass — he was in the room, the model saw six frames.
    """
    if (description or {}).get("product_confirmed"):
        return False
    guess = (description or {}).get("product_guess", "") or ""
    g = guess.strip().lower()
    return (not g) or g.startswith("unclear") or "cannot be confirmed" in g \
        or "not sure" in g or g in ("none", "unknown", "n/a")


def choose_style(recent=None, description=None):
    """Rotation, never random. Recency filter first, then least recently used.

    Mirrors Stage 2 of the image lane so the two lanes share one rotation
    history and neither collapses into a single shape.
    """
    recent = recent if recent is not None else read_recent_styles()
    eligible = list(reel_config.REEL_ELIGIBLE_STYLES)

    # You cannot "meet" a product nobody could identify. Without this the lane
    # writes a confident product introduction over footage it could not read.
    if description is not None and product_is_unclear(description):
        eligible = [s for s in eligible if s != "Meet the Product"]
        log("  product unclear -> 'Meet the Product' excluded this run")

    blocked = set(recent[:reel_config.REEL_STYLE_NO_REPEAT_WITHIN])
    fresh = [s for s in eligible if s not in blocked]
    pool = fresh or eligible          # never return nothing

    def last_used(style):
        try:
            return recent.index(style)
        except ValueError:
            return len(recent) + 1    # never used = most overdue
    pool.sort(key=lambda s: -last_used(s))
    chosen = pool[0]
    log(f"  style: {chosen} (recent: {', '.join(recent[:4]) or 'none logged'})")
    return chosen


def _overlay_rule(description):
    if description.get("has_text_overlay"):
        return ("IMPORTANT: this video already has words burned into it. The\n"
                "caption must not repeat them or paraphrase them. Say the thing\n"
                "the on-screen text does not.")
    return ("This video carries no on-screen text, so the caption is the only\n"
            "language the viewer gets. It still must not narrate the footage.")


HOOK_RULES = {
    "caption": (
        "The caption MUST BEGIN WITH THIS EXACT LINE, character for character:\n\n"
        "    {hook}\n\n"
        "Do not reword it, re-punctuate it, or fold it into a longer sentence.\n"
        "It is the variable under test: if you change it, the experiment this\n"
        "post exists to run is ruined. Continue the caption after it."),
    "overlay": (
        "This video already has these words burned onto its opening seconds:\n\n"
        "    {hook}\n\n"
        "The viewer has read them. DO NOT repeat or paraphrase them anywhere in\n"
        "the caption. Say the thing the on-screen hook does not."),
}


def _taste(state):
    try:
        import reel_feedback
        return reel_feedback.taste_block(state or {}, "caption")
    except Exception as e:
        log(f"  feedback unavailable ({type(e).__name__}) — writing without it")
        return "(feedback unavailable this run)"


def write_caption(description, work_dir, style=None, attempts=2,
                  hook=None, hook_mode="caption", state=None):
    """Returns (caption, style, meta). Raises on failure — the caller parks
    the video rather than publishing an unvalidated caption."""
    os.makedirs(work_dir, exist_ok=True)
    style = style or choose_style(description=description)
    out_path = os.path.join(work_dir, "caption.json")

    template, version = load_prompt("reel-caption")
    recent = read_recent_styles()

    if hook:
        hook_rule = HOOK_RULES[hook_mode].format(hook=hook)
    else:
        hook_rule = ("No hook was set for this post. Open the caption however\n"
                     "the style calls for.")

    prompt = template.format(
        summary=description.get("summary", ""),
        on_screen=description.get("on_screen", ""),
        product_guess=description.get("product_guess", "unclear"),
        fabric_guess=description.get("fabric_guess", "unclear"),
        mood=description.get("mood", ""),
        hook=description.get("hook", ""),
        has_text_overlay=("yes" if description.get("has_text_overlay") else "no"),
        seo_terms=", ".join(description.get("seo_terms") or []),
        overlay_rule=_overlay_rule(description),
        hook_rule=hook_rule,
        claims=__import__("reel_hook").load_claims(),
        taste=_taste(state),
        taste_brief=__import__("reel_hook")._taste_brief("reel-caption"),
        style=style,
        style_spec=STYLE_SPECS[style],
        recent_styles=", ".join(recent[:6]) or "none logged yet",
        out_path=out_path,
    )

    last_problem = ""
    for attempt in range(1, attempts + 1):
        ok, result = invoke_claude_json(
            prompt, work_dir, out_path,
            schema=CAPTION_SCHEMA, stage="caption", timeout=420)
        if not ok:
            last_problem = str(result)
            continue

        caption = result["caption"].strip()
        valid, why = validate_caption(caption, style)

        # Do not let the hashtags assert a product the vision pass refused to
        # name. This is the same class of error as a number in a hook: a claim
        # we cannot stand behind, published autonomously.
        if valid and product_is_unclear(description):
            bad = unverified_product_tags(caption)
            if bad:
                valid = False
                why = (f"hashtags claim a product the video could not be "
                       f"confirmed to show: {', '.join(bad)}")

        # VERIFY the hook survived. Asking is not the same as checking: a
        # reworded hook silently breaks run-over-run comparison.
        if valid and hook and hook_mode == "caption":
            first = caption.split("\n")[0].strip()
            if not first.startswith(hook.rstrip(".!").strip()):
                valid = False
                why = (f"caption must open with the hook verbatim; it opens "
                       f"with {first[:60]!r} instead")

        if valid:
            log(f"  caption validated ({style}, prompt {version})")
            return caption, style, {
                "prompt_version": version,
                "seo_phrase_used": result.get("seo_phrase_used", ""),
                "reasoning": result.get("reasoning", ""),
            }

        last_problem = why
        log(f"  caption REJECTED: {why}")
        prompt = (f"{prompt}\n\n---\nYOUR PREVIOUS CAPTION WAS REJECTED BY THE "
                  f"VALIDATOR: {why}.\nWrite the corrected JSON to {out_path} "
                  f"again. Keep the style {style}. Fix only the stated problem.")

    # THE SAFETY GATE. Marcus's one condition on running this unattended was
    # that captions never go "too wild". An unvalidated caption is never
    # published; the video is parked and the reason is logged.
    raise ValueError(f"caption failed validation after {attempts} attempts: "
                     f"{last_problem}")


# Product nouns Selene sells. Naming one of these in a hashtag is a CLAIM about
# what is in the video, so it needs the vision pass to have actually seen it.
PRODUCT_NOUNS = (
    "throw", "duvet", "duvetcover", "sheet", "sheets", "sheetset",
    "pillowcase", "pillowcases", "pillow", "eyemask", "sleepmask",
    "blanket", "bedding", "beddingset", "comforter", "quilt", "coverlet",
    "flatsheet", "fittedsheet", "bedsheet", "bedsheets", "robe", "sham",
)


def unverified_product_tags(caption):
    """Hashtags that name a product when the product was not identified."""
    lines = [l.strip() for l in caption.split("\n") if l.strip()]
    if not lines:
        return []
    tags = [t for t in lines[-1].split() if t.startswith("#")]
    hits = []
    for tag in tags:
        body = tag[1:].lower()
        if body == "selenedreams":
            continue
        for noun in PRODUCT_NOUNS:
            if noun in body:
                hits.append(tag)
                break
    return hits


def log_rotation(video_name, style, product):
    """Share the image lane's rotation log so both lanes stay coherent."""
    append_caption_log(
        number=video_name, lane="reel", product=product or "unclear",
        style=style, route="reel/trial", tags="")
