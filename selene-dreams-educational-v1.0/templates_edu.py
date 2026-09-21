# =============================================================================
# templates_edu.py — Selene Educational Carousel template kit
# VERSION 1.9 — 2026-09-09
# CHANGELOG
#   1.9  2026-09-09  CAPS MEASURED, NOT GUESSED. cover_editorial flagged three
#                    separate topics on its title, so I measured what actually
#                    fits instead of trusting the numbers: cap 34 but only 21-22
#                    characters of real prose fit two lines at 118px. cover_hero
#                    was worse (cap 46, 25 fit). The max_lines check has been
#                    quietly catching these in rewrite round 2 all along, which
#                    is why it looked fine - the writer was being told a cap it
#                    could not use, then corrected after wasting a round.
#                    Caps are now the measured figure for ordinary English:
#                      cover_hero title      46 -> 34
#                      cover_editorial title 34 -> 22
#                      bubble_card desc      80 -> 78
#                    max_lines remains the real guarantee; max_chars is now
#                    honest guidance rather than a number that misleads. Set to
#                    the ORDINARY-PROSE figure, not the all-long-words worst case:
#                    the worst case would have rejected copy Marcus had already
#                    approved and that renders correctly.
#   1.8  2026-09-09  SERIES_FOR: topic type -> the recurring series name the
#                    Topic Guide uses (writer and caption stages need it).
#                    Real Moments added to the map.
#   1.7  2026-09-09  OUTRO DROPPED from every plan (Marcus: redundant, not
#                    clean). Posts now end on their last real slide. The outro
#                    TEMPLATE is kept in TEMPLATES, just unused by any plan, so
#                    it can be re-added without rebuilding it.
#                    Bubble description cap 72 -> 80. The old number was
#                    measured against uniform filler; real prose packs better
#                    and 72 was strangling the conversational tone Marcus
#                    wants. max_lines 2 is still the real guard - a string can
#                    clear 80 chars and still overflow, and the renderer will
#                    raise when it does.
#   1.6  2026-09-09  TWO ARCHETYPES, NOT A HYBRID. Marcus caught that v1.5's
#                    interleaved plans (cover, bubble, photo, bubble, photo)
#                    are a shape he has NEVER posted. Regrouping the reference
#                    folder by export timestamp proved it: his 5 no-text
#                    interiors are ONE post (Dec 19, cover + 5 bare photos) and
#                    his 3 bubble interiors are a DIFFERENT post (Nov 24, cover
#                    + 3 bubbles + outro). v1.5 averaged across posts and
#                    invented a third shape. Now:
#                      ARCHETYPE B "taught"  = cover + bubble on every interior
#                                              + outro. All 9 original types.
#                      ARCHETYPE A "shown"   = cover + bare photos, text on the
#                                              thumbnail only, NO outro.
#                    Archetype follows the TOPIC TYPE (Marcus's call) so he
#                    never picks per post. New 10th type "Real Moments" carries
#                    archetype A - named from his own cover, Frame Copy 112.
#                    image_only no longer appears in any other type's plan.
#   1.5  2026-09-01  DEFAULT_PLANS rebuilt to the reference shape (Marcus's
#                    call): the cover carries the hook, one to three bubble
#                    slides carry the lesson, every other interior is
#                    image_only. Added COVER_CYCLE — the four cover templates
#                    rotate across posts so no two consecutive posts share one.
#   1.4  2026-09-01  THREE MORE COVERS, measured off Marcus's layout_reference
#                    folder: cover_plain (centred, NO rule), cover_editorial
#                    (left-aligned, oversized title top-left) and
#                    cover_title_only (title alone, sitting low). cover_hero
#                    keeps the rule and is now one of four, not the only one.
#                    No change to any existing template's geometry.
#   1.3  2026-08-29  bubble_card switched to a self-sizing stack; outro title
#                    boxed narrower so it breaks over two lines like the
#                    reference.
#   1.2  2026-08-29  THE REFERENCE SET. Three templates copied from Marcus's own
#                    best posts: cover_hero (full-bleed photo, big uppercase
#                    title, rule, two small lines), bubble_card (frosted panel
#                    bottom-left, title case name + one description line), and
#                    outro (flat ecru, SELENE DREAMS + visit line, optional).
#   1.1  2026-08-28  Added title_card: short uppercase Roumald title + one small
#                    Inter description, the shape of Marcus's best-performing
#                    posts ("LINEN'S WINTER SECRET" + one line). Caps are
#                    deliberately brutal: 34 chars title, 70 description.
#   1.0  2026-08-28  v1 kit derived from the NAA brand guidelines (not yet from
#                    Marcus's past posts — proof-sheet corrections expected).
#                    Six templates: hook_cover, body, list, quote, image_only, cta.
#                    Character caps measured against real fonts at real sizes.
# =============================================================================
# Every template: which text zones exist, font role, size, position, alignment,
# colour logic, and a hard character cap (overflow = rewrite, never shrink).
#
# Layout language: canvas 1080x1350, margins 70, brand corner radius 15.
# y positions are fractions of canvas height. "scrim" = rounded rectangle behind
# text when the background is an image (legibility fallback).

TEMPLATES = {
    # --- the reference set (v1.2), modelled on Marcus's real posts -----------
    "cover_hero": {
        "desc": "Slide 1. Full-bleed photo, big uppercase title, rule, 2 small lines.",
        "zones": [
            {"name": "title", "font": "roumald_bold", "size": 96, "y": 0.345,
             "align": "center", "upper": True, "leading": 1.06, "ink": "winter",
             "max_chars": 34, "max_lines": 2},   # measured 2026-09-09: 25-40 depending on word length
            {"name": "desc", "font": "inter", "size": 33, "y": 0.573,
             "align": "center", "leading": 1.36, "ink": "winter", "anchor": "top",
             "max_chars": 84, "max_lines": 2, "optional": True},
        ],
        "rule": {"y": 0.518, "x0": 0.17, "x1": 0.83, "thickness": 2, "ink": "winter"},
    },
    "bubble_card": {
        "desc": "Interior slide. Photo + frosted bubble bottom-left, title case + one line.",
        "stack": {"x": 0.093, "w": 0.500, "bottom": 0.866, "gap": 22,
                  "pad_x": 0.042, "pad_top": 0.030, "pad_bottom": 0.026,
                  "panel": {"radius": 62, "blur": 20, "tint": "#F5F3EF", "alpha": 0.16}},
        "zones": [
            {"name": "title", "font": "roumald_roman", "size": 62,
             "align": "left", "leading": 1.14, "ink": "winter",
             "max_chars": 40, "max_lines": 2},
            {"name": "desc", "font": "inter", "size": 29,
             "align": "left", "leading": 1.33, "ink": "winter",
             "max_chars": 78, "max_lines": 2},   # measured 2026-09-09: 78 for ordinary prose (68 worst case, all-long-words)
        ],
    },
    "cover_plain": {
        "desc": "Slide 1, NO rule. Uppercase title centred upper-middle, small line below.",
        "zones": [
            {"name": "title", "font": "roumald_bold", "size": 96, "y": 0.400,
             "align": "center", "upper": True, "leading": 1.10, "ink": "winter",
             "max_chars": 46, "max_lines": 3},
            {"name": "desc", "font": "inter", "size": 33, "y": 0.615,
             "align": "center", "leading": 1.45, "ink": "winter", "anchor": "top",
             "max_chars": 84, "max_lines": 2, "optional": True},
        ],
    },
    "cover_editorial": {
        "desc": "Slide 1, LEFT aligned. Oversized title top-left, description lower-left.",
        "zones": [
            {"name": "title", "font": "roumald_bold", "size": 118, "y": 0.185,
             "x": 0.065, "w": 0.780, "align": "left", "upper": True, "leading": 1.16,
             "ink": "winter", "anchor": "top", "max_chars": 22, "max_lines": 2},   # measured: 21 worst case
            {"name": "desc", "font": "inter", "size": 34, "y": 0.700,
             "x": 0.065, "w": 0.560, "align": "left", "leading": 1.45, "ink": "winter",
             "anchor": "top", "max_chars": 96, "max_lines": 3, "optional": True},
        ],
    },
    "cover_title_only": {
        "desc": "Slide 1, title alone, sitting LOW. No rule, no description.",
        "zones": [
            {"name": "title", "font": "roumald_bold", "size": 96, "y": 0.670,
             "align": "center", "upper": True, "leading": 1.10, "ink": "winter",
             "max_chars": 40, "max_lines": 2},
        ],
    },
    "outro": {
        "desc": "Optional last slide. Flat ecru, SELENE DREAMS + visit line.",
        "zones": [
            {"name": "title", "font": "roumald_bold", "size": 100, "y": 0.407,
             "align": "center", "upper": True, "leading": 1.10, "ink": "moss",
             "x": 0.21, "w": 0.58, "max_chars": 26, "max_lines": 2},
            {"name": "desc", "font": "roumald_roman", "size": 40, "y": 0.567,
             "align": "center", "ink": "moss", "max_chars": 46, "optional": True},
        ],
    },
    "title_card": {
        "desc": "Short title + one small description line. Cover or interior.",
        "zones": [
            {"name": "title", "font": "roumald_bold", "size": 78, "y": 0.45,
             "align": "center", "upper": True, "leading": 1.10,
             "max_chars": 34, "max_lines": 2},
            {"name": "desc", "font": "inter", "size": 32, "y": 0.57,
             "align": "center", "leading": 1.35, "max_chars": 70,
             "max_lines": 2, "optional": True},
        ],
    },
    "hook_cover": {
        "desc": "Slide 1. Big Roumald title, centred. Over image or flat.",
        "zones": [
            {"name": "kicker", "font": "roumald_roman", "size": 30, "y": 0.16,
             "align": "center", "upper": True, "tracking": 2, "max_chars": 28, "optional": True},
            {"name": "title", "font": "roumald_bold", "size": 92, "y": 0.42,
             "align": "center", "upper": True, "leading": 1.10, "max_chars": 70, "max_lines": 4},
            {"name": "footer", "font": "inter", "size": 26, "y": 0.88,
             "align": "center", "max_chars": 36, "optional": True},
        ],
    },
    "body": {
        "desc": "Teaching slide. Small Roumald header + Inter body block.",
        "zones": [
            {"name": "header", "font": "roumald_bold", "size": 48, "y": 0.22,
             "align": "left", "upper": True, "max_chars": 40, "max_lines": 2, "optional": True},
            {"name": "body", "font": "inter", "size": 40, "y": 0.40,
             "align": "left", "leading": 1.30, "max_chars": 240, "max_lines": 9},
        ],
    },
    "list": {
        "desc": "Numbered/step slide. Big number + Inter body.",
        "zones": [
            {"name": "number", "font": "roumald_bold", "size": 120, "y": 0.18,
             "align": "left", "max_chars": 12},
            {"name": "body", "font": "inter", "size": 40, "y": 0.42,
             "align": "left", "leading": 1.30, "max_chars": 220, "max_lines": 8},
        ],
    },
    "quote": {
        "desc": "Single thought, Roumald Italic, centred. Inspirational default.",
        "zones": [
            {"name": "quote", "font": "roumald_italic", "size": 66, "y": 0.44,
             "align": "center", "leading": 1.15, "max_chars": 130, "max_lines": 5},
            {"name": "attribution", "font": "inter", "size": 26, "y": 0.82,
             "align": "center", "max_chars": 40, "optional": True},
        ],
    },
    "image_only": {
        "desc": "No text. Background passes through untouched (metadata strip only).",
        "zones": [],
    },
    "cta": {
        "desc": "Closing slide. Roumald line + Inter footer with the site.",
        "zones": [
            {"name": "line", "font": "roumald_bold", "size": 64, "y": 0.40,
             "align": "center", "upper": True, "leading": 1.12, "max_chars": 90, "max_lines": 4},
            {"name": "footer", "font": "inter", "size": 30, "y": 0.80,
             "align": "center", "max_chars": 40, "optional": True},
        ],
    },
}

# Default template plan per topic type — the plan builder starts here and the
# plan is always visible/editable in the queue row before Marcus approves.
DEFAULT_PLANS = {
    # --- ARCHETYPE B, "taught": every slide speaks. NO outro (v1.7) ----------
    "Fabric Education":            ["cover_plain", "bubble_card", "bubble_card", "bubble_card", "bubble_card", "bubble_card"],
    "Myth-Busting":                ["cover_plain", "bubble_card", "bubble_card", "bubble_card", "bubble_card"],
    "Care & How-To":               ["cover_plain", "bubble_card", "bubble_card", "bubble_card", "bubble_card"],
    "Buying Guide":                ["cover_plain", "bubble_card", "bubble_card", "bubble_card", "bubble_card", "bubble_card"],
    "Sleep Rituals / Slow Living": ["cover_plain", "bubble_card", "bubble_card", "bubble_card", "bubble_card"],
    "Styling & Home":              ["cover_plain", "bubble_card", "bubble_card", "bubble_card", "bubble_card"],
    "Behind Selene":               ["cover_plain", "bubble_card", "bubble_card", "bubble_card", "bubble_card"],
    "Fun & Relatable":             ["cover_plain", "bubble_card", "bubble_card", "bubble_card", "bubble_card"],
    "Inspirational":               ["cover_plain", "bubble_card", "bubble_card"],

    # --- ARCHETYPE A, "shown": text on the thumbnail only --------------------
    "Real Moments":                ["cover_editorial", "image_only", "image_only", "image_only", "image_only", "image_only"],
}

# Topic type -> recurring series name (Post Topic sheet, "Topic Guide" tab).
SERIES_FOR = {
    "Fabric Education":            "Fabric Face-Offs",
    "Myth-Busting":                "Honest Bedding",
    "Care & How-To":               "Care Rituals",
    "Buying Guide":                "Find Your Fabric",
    "Sleep Rituals / Slow Living": "Wind Down",
    "Styling & Home":              "Make the Bed",
    "Behind Selene":               "The Selene Story",
    "Fun & Relatable":             "Bedtime Company",
    "Inspirational":               "Gentle Reminders",
    "Real Moments":                "Real Moments",
}

# Types whose carousels carry text on the COVER ONLY. The words gate for these
# is just the thumbnail line; slides 2-7 stay empty in the Post Topic sheet.
PHOTO_ESSAY_TYPES = {"Real Moments"}

# Templates that need no text from the sheet.
NO_TEXT_TEMPLATES = {"image_only"}

# Cover rotation. plan_edu walks these by POSITION and never gives two
# consecutive posts the same cover.
# cover_hero is deliberately ABSENT from the photo-essay cycle: its rule and
# description set up a list, which a wordless carousel then fails to deliver.
COVER_CYCLE = ["cover_plain", "cover_hero", "cover_editorial", "cover_plain", "cover_title_only"]
COVER_CYCLE_PHOTO_ESSAY = ["cover_editorial", "cover_title_only", "cover_plain"]
COVER_TEMPLATES = ["cover_hero", "cover_plain", "cover_editorial", "cover_title_only"]

def cap_for(template, zone_name):
    for z in TEMPLATES[template]["zones"]:
        if z["name"] == zone_name:
            return z["max_chars"]
    return None
