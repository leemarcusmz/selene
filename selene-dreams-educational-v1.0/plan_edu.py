# =============================================================================
# plan_edu.py — builds a visible, editable image plan for each approved topic
# VERSION 2.2 — 2026-09-16
# CHANGELOG
#   2.2  2026-09-16  {taste_brief} in the picker prompt (picker_edu.md v3).
#   2.1  2026-09-16  MARCUS'S EDUCATIONAL REFERENCES. The picker prompt now
#                    carries {reference_section}: images from Drive
#                    "02. Reference Images / 02. Educational" (reference_drive
#                    in v3.0, on sys.path) with their vision notes, viewed
#                    before choosing. Style only: they steer which library
#                    photo is picked and the mood asked of a generation;
#                    they never enter the generator. Fail-open.
#   2.0  2026-09-10  THE PICKER (Marcus's matching design, 2026-09-10). When a
#                    topic has visual briefs (brief_edu, Post Topic N-T), the
#                    plan is chosen by ONE Claude call per post: every slide's
#                    brief against every eligible library image's description,
#                    returning a pick with a confidence and a one-line reason,
#                    or null = generate. Hard rules run in code before the call
#                    (non-brand out, ids in live rows out, cover-eligible for
#                    covers) and after it (no id twice, one per shoot, confidence
#                    floor C.PICK_MIN_CONFIDENCE). The reason lands in the Slide
#                    Source cell so Marcus can see WHY. A GEN prompt is the brief
#                    itself in the brand look. Topics without briefs fall back to
#                    the v1.8 keyword matcher unchanged.
#   1.8  2026-09-10  SLIDE-LEVEL MATCHING. Marcus on the first live post (#16):
#                    "the thumbnail product doesn't even look like ours" and
#                    "what's written on the slides doesn't match the images".
#                    Both true, and structural: images were matched on TOPIC
#                    TYPE keywords only ("calm" hits half a library of 50), the
#                    slide copy was never consulted, and nothing stopped a
#                    quilted comforter - not a Selene product - taking a cover.
#                    Now: (1) each slide scores library images against ITS OWN
#                    words plus the type words; below C.REUSE_MIN_SCORE the slide
#                    GENERATES from a prompt written from the slide copy, so the
#                    picture says what the bubble says; (2) C.NON_BRAND_TAGS
#                    (quilt, striped, velvet...) can never be reused anywhere;
#                    (3) an image already in ANY live queue row is off the table
#                    for a new row, not just covers - #12 and #16 had shared three
#                    of five photos; (4) replan(number) rebuilds one existing row
#                    in place for exactly this situation.
#   1.7  2026-09-09  BUG: the one-per-shoot rule read the SUBJECT column for the
#                    shoot folder, but tag_library.py overwrote that column with
#                    real tags - so after tagging the rule matched nothing and a
#                    Buying Guide post drew IMG-0001..0007, i.e. two frames from
#                    Row 22 and three from Row 23, exactly the fault it existed to
#                    prevent. The shoot folder lives in the SOURCE column
#                    ("v3.0 flow: 2026/08. August/Row 22"); read that instead.
#   1.6  2026-09-09  IMAGE SOURCING FIXES, from running the planner against the
#                    real 50-image library.
#                    (a) VARIETY: picks were ordered by least-used only, so a
#                        Fabric Education post drew six consecutive frames from
#                        Row 22 and Row 23 - the same sheet set, same colourway,
#                        on every slide. A post now takes at most ONE image per
#                        shoot folder, and falls back to a generation rather than
#                        repeating a shoot.
#                    (b) The keyword map matched the Drive PATH, so "bed" hit 0 of
#                        50 files and forced Buying Guide and Styling & Home to
#                        generate every slide, while "Row" hit 45 of 50 and let
#                        any image answer a wind-down post. Keywords now read the
#                        real subject/mood tags that tag_library.py writes, and
#                        each type carries several terms instead of one.
#                    (c) PARKED types are skipped entirely.
#   1.5  2026-09-09  Works with writer_edu: honours a "cover=<template>" the
#                    writer recorded in the topic remark (so the caps the copy
#                    was validated against are the caps it renders with);
#                    rotation_state()/queued_topic_nums() factored out so both
#                    stages read the same state; queue rows whose Notes say
#                    SUPERSEDED are ignored, which is how rows 1-9 (planned under
#                    the old rules) get re-planned without deleting anything.
#   1.4  2026-09-09  ARCHETYPE-AWARE. Follows templates_edu v1.6's split into
#                    "taught" and "shown" plans.
#                    BUG FIX (blocker for photo-essay posts): slide count came
#                    from the number of NON-EMPTY slide-text cells, so a
#                    thumbnail-text-only post would have collapsed to a ONE
#                    slide carousel. Slide count now comes from the plan, and
#                    text-needing slides are trimmed only when the sheet has
#                    fewer lines than the plan asks for; image_only slides never
#                    need a cell and the outro fills from brand constants.
#                    Cover rotation now uses the photo-essay cycle for
#                    photo-essay types (no cover_hero - see templates_edu).
#   1.3  2026-09-01  COVER ROTATION: slide 1's template is chosen from
#                    COVER_CYCLE, never repeating the previous post's cover.
#                    BUG FIX: bubble_card slides were being given FLAT
#                    backgrounds — the frosted panel only draws over a photo, so
#                    those slides rendered as bare text on a flat colour. Every
#                    photo-backed template (covers + bubble_card + image_only)
#                    now sources a real image; FLAT is left for outro only.
#   1.2  2026-08-28  Cover dedupe across ROWS: a library image already planned
#                    or used as any row's cover is excluded from later cover
#                    picks (batch-wide and against existing queue rows).
#   1.1  2026-08-28  429 quota fix: library loaded once per sync and passed
#                    down; queue rows appended in ONE batch; status rows written
#                    in ONE batch update.
#   1.0  2026-08-28  First release. Approved Post Topic rows become queue rows
#                    with a per-slide plan (FLAT / REUSE <id> / GEN: <prompt>).
#                    Nothing generates from here — the plan waits for Marcus's
#                    D=Approved in Generation Status.
# =============================================================================
import datetime, re
import config_edu as C
import sheets_edu as S
import library_edu as L
from templates_edu import (DEFAULT_PLANS, COVER_CYCLE, COVER_CYCLE_PHOTO_ESSAY,
                           COVER_TEMPLATES, PHOTO_ESSAY_TYPES, NO_TEXT_TEMPLATES, SERIES_FOR)

# Brand photography direction (NAA deck): the GEN prompt skeleton.
PROMPT_BASE = ("Editorial photograph for a premium natural-bedding brand. {scene} "
               "Natural light at dusk or dawn with a warm glow, soft and ethereal mood, "
               "serene, subtle film grain, muted natural palette of moss green, ecru and "
               "winter white. No text, no logos, no visible faces.")

SCENES = {
    "Fabric Education": "Close-up of natural linen and crisp percale bedding side by side on a calm bed, textures clearly visible.",
    "Myth-Busting": "Macro close-up of woven natural cotton fabric, individual threads and weave structure visible.",
    "Care & How-To": "Softly rumpled washed linen drying near a window, gentle morning light.",
    "Buying Guide": "A calm bed dressed in layered natural bedding beside a large window at dawn.",
    "Sleep Rituals / Slow Living": "A dim, serene bedroom at dusk, made bed, warm lamplight, a sense of quiet.",
    "Styling & Home": "A beautifully layered bed styled with natural bedding, throw draped off one corner.",
    "Behind Selene": "Hands smoothing folded natural linen on a wooden table, craft feeling, anonymous.",
    "Fun & Relatable": "A lived-in bed mid-morning, duvet askew, warm and human, nobody visible.",
    "Inspirational": "A soft abstract close-up of ecru linen texture filling the frame.",
}

# What each topic type wants to see. Matched against the library's SUBJECT and
# MOOD tags (written by tag_library.py), first term that finds a free image wins.
# Never match on the Drive path again: "bed" hit 0 of 50 filenames and "Row" hit 45.
TYPE_KEYWORDS = {
    "Fabric Education":            ["texture", "weave", "fabric", "linen", "percale"],
    "Myth-Busting":                ["texture", "weave", "percale", "fabric"],
    "Care & How-To":               ["linen", "folded", "laundry", "texture"],
    "Buying Guide":                ["bed", "bedding", "styled", "sheet"],
    "Sleep Rituals / Slow Living": ["calm", "evening", "lamp", "bedroom", "quiet"],
    "Styling & Home":              ["styled", "bed", "layered", "bedroom"],
    "Behind Selene":               ["hands", "folded", "craft", "linen"],
    "Fun & Relatable":             ["lived in", "morning", "rumpled", "bed"],
    "Real Moments":                ["bedroom", "morning", "calm", "bed"],
}


def _keywords(topic_type):
    return TYPE_KEYWORDS.get(topic_type, [])


def _shoot_of(row):
    """The shoot a library image came from, e.g. '2026/08. August/Row 22'.
    Two frames from one shoot are near-identical, so a post takes at most one.
    NOTE: read SOURCE, not SUBJECT — tag_library.py replaces subject with real
    tags, and reading subject here silently disabled this rule once it had run."""
    src = (row.get("source") or "").strip()
    if not src:
        return ""
    return src.split(":", 1)[1].strip() if ":" in src else src


_STOP = set("""the and for you your with that this from into onto over under when then than
what which while where here there they them their will just very more most some
each every about after before because also only even still both once ever never
like into make makes made take takes took keep keeps kept feel feels felt look
looks looked read reads reading choose chooses pick picks want wants need needs
first last next later early soon does done doing have having been being were
matters matter rather stay stays gets goes come comes something anything nothing
one two three four five six seven eight nine ten it its off out own how why who
not but yet all any few lot lots way ways thing things time times""".split())


def _slide_terms(slide_text):
    """Content words from one slide cell (title | description), crudely stemmed."""
    words = re.findall(r"[a-z]+", (slide_text or "").lower())
    out = set()
    for w in words:
        if len(w) < 4 or w in _STOP:
            continue
        w = re.sub(r"(ing|ers|er|es|s)$", "", w) if len(w) > 5 else w.rstrip("s")
        out.add(w)
    return out


def _non_brand(row):
    tags = (row["subject"] + " " + row["mood"]).lower()
    return any(t in tags for t in C.NON_BRAND_TAGS)


def _score(row, terms, type_terms):
    """(total, slide_hits). An interior slide needs at least one hit on ITS OWN
    words - type words alone ("bed", "bedroom", "calm") describe half the library
    and are exactly how "Turn The Bed Down" got a meadow."""
    toks = set(re.findall(r"[a-z]+", (row["subject"] + " " + row["mood"]).lower()))
    def hit(term):   # stem must START a tag word: "room" is not in "bedroom"
        return any(tok.startswith(term) for tok in toks)
    slide_hits = sum(1 for t in terms if t and hit(t))
    type_hits = sum(1 for t in type_terms if all(hit(w) for w in t.lower().split()))
    return slide_hits * 2 + type_hits, slide_hits


def _pick(keywords, lib_rows, exclude_ids, used_shoots, need_cover=False,
          slide_text=""):
    """Best-scoring free library image for THIS slide, or None when nothing
    scores at least C.REUSE_MIN_SCORE. Ties go to the least-used image."""
    terms = _slide_terms(slide_text)
    type_terms = keywords or []
    cands = []
    for r in lib_rows:
        if r["id"] in exclude_ids or _non_brand(r):
            continue
        if need_cover and r["eligible"] != "Yes":
            continue
        if C.REUSE_ONE_PER_SHOOT and _shoot_of(r) in used_shoots:
            continue
        sc, slide_hits = _score(r, terms, type_terms)
        if sc < C.REUSE_MIN_SCORE:
            continue
        if not need_cover and terms and slide_hits == 0:
            continue    # a bubble slide must match its own words, not just the type
        cands.append((-sc, int(r["used"] or 0), r))
    if not cands:
        return None
    cands.sort(key=lambda x: (x[0], x[1]))
    return cands[0][2]


def _gen_prompt(ttype, slide_text):
    """A GEN prompt that says what the slide says, in the brand look."""
    title, _, desc = (slide_text or "").partition("|")
    title, desc = title.strip().rstrip("."), desc.strip()
    scene = SCENES.get(ttype, SCENES["Fabric Education"])
    if title or desc:
        scene = (f"{scene} The picture must visually express the idea "
                 f"\"{title}\"{(': ' + desc) if desc else ''} - show the moment or "
                 f"the object the words are about, not a generic bed.")
    return PROMPT_BASE.format(scene=scene)

# Templates that need a real photograph behind them. Everything here sources a
# library image or a generation; only outro (and legacy flat templates) get FLAT.
PHOTO_TEMPLATES = set(COVER_TEMPLATES) | {"bubble_card", "image_only", "title_card",
                                          "hook_cover", "quote"}


def _fit_plan(plan, n_texts):
    """How many slides this row actually gets.

    The PLAN decides the shape, not the number of filled text cells - a
    photo-essay row has one line of copy and still runs six slides. Slides that
    need a text cell (covers, bubbles) are trimmed from the end only when the
    sheet has fewer lines than the plan asks for; image_only never needs a cell
    and the outro fills itself from the brand constants."""
    tail = [t for t in plan if t == "outro"]
    body = [t for t in plan if t != "outro"]
    out, used = [], 0
    for t in body:
        if t in NO_TEXT_TEMPLATES:
            out.append(t)
            continue
        if used < n_texts:
            out.append(t)
            used += 1
        else:
            break
    return (out + tail)[:C.MAX_SLIDES]


def _cycle_for(topic_type):
    return COVER_CYCLE_PHOTO_ESSAY if topic_type in PHOTO_ESSAY_TYPES else COVER_CYCLE


PICK_SCHEMA = {"picks": {"type": "list", "required": True, "min_len": 1}}


def _eligible(lib_rows, taken):
    out = []
    for r in lib_rows:
        if r["id"] in taken or (r.get("non_brand") or "").lower().startswith("y"):
            continue
        if _non_brand(r):
            continue
        if not (r.get("description") or "").strip():
            continue                  # untagged v1 row: nothing to match against
        out.append(r)
    return out


def _library_block(rows):
    lines = []
    for r in rows:
        bits = [f"{r['id']}: {r['description']}"]
        extra = []
        if r.get("setting"):  extra.append(f"setting: {r['setting']}")
        if r.get("action") and r["action"] != "none": extra.append(f"action: {r['action']}")
        if r.get("people") and r["people"] != "none": extra.append(f"people: {r['people']}")
        if r.get("light"):    extra.append(f"light: {r['light']}")
        extra.append(f"cover: {r.get('eligible') or 'No'}")
        extra.append(f"ours: {r.get('ours') or 'No'}" + (f" ({r['product']})" if r.get("product") else ""))
        extra.append(f"used: {r.get('used') or 0}")
        extra.append(f"shoot: {_shoot_of(r) or '-'}")
        lines.append("  " + bits[0] + "\n      " + " · ".join(extra))
    return "\n".join(lines)


def pick_images(topic, templates, briefs, lib_rows, taken):
    """One Claude call: brief per slide vs every eligible image. Returns a list
    (len = len(templates)) of (row_or_None, confidence, reason), or None when
    the call itself failed (caller falls back to keywords)."""
    import os, re as _re, tempfile, shutil
    from claude_client import invoke_claude_json
    cands = _eligible(lib_rows, taken)
    if not cands:
        return [(None, 0.0, "library has no eligible described images")] * len(templates)
    texts = [s for s in topic["slides"] if s.strip()]
    ti, lines = 0, []
    for i, tmpl in enumerate(templates, 1):
        kind = "COVER" if i == 1 else ("PHOTO ONLY" if tmpl in NO_TEXT_TEMPLATES else "INTERIOR")
        words = ""
        if tmpl not in NO_TEXT_TEMPLATES and ti < len(texts):
            words = texts[ti]; ti += 1
        brief = briefs[i - 1] if i - 1 < len(briefs) else ""
        lines.append(f"  slide {i} [{kind}] words: {words.strip() or '(none)'}\n"
                     f"      brief: {brief.strip() or '(no brief)'}")
    path = os.path.join(C.PROMPT_DIR, "picker_edu.md")
    with open(path) as f:
        tpl = f.read()
    try:
        import reference_drive
        reference_drive.refresh()
        reference_section = reference_drive.section(
            "educational", heading="MARCUS'S EDUCATIONAL REFERENCES")
    except Exception as _e:
        reference_section = ""
    try:
        import taste_brief
        brief = taste_brief.brief_block("picker_edu")
    except Exception:
        brief = "(taste brief unavailable this run)"
    m = _re.search(r"<!--\s*VERSION:\s*([^\s>]+)\s*-->", tpl)
    ver = m.group(1) if m else "unversioned"
    workdir = tempfile.mkdtemp(prefix=f"selene_pick_{topic['num']}_")
    try:
        out_path = os.path.join(workdir, "picks.json")
        prompt = tpl.format(topic_type=topic["type"], series=SERIES_FOR.get(topic["type"], topic["type"]),
                            topic_desc=topic["desc"] or "(no description)",
                            slides_block="\n".join(lines), library_block=_library_block(cands),
                            reference_section=reference_section, taste_brief=brief,
                            n_slides=len(templates), min_confidence=C.PICK_MIN_CONFIDENCE,
                            out_path=out_path)
        from log_edu import log
        log(f"  picker: topic #{topic['num']} ({ver}), {len(templates)} slide(s) vs {len(cands)} image(s)")
        ok, res = invoke_claude_json(prompt, workdir, out_path, schema=PICK_SCHEMA,
                                     stage="picker_edu", timeout=C.WRITER_TIMEOUT)
        if not ok:
            log(f"  picker BLOCKED: {res}")
            return None
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    by_id = {r["id"]: r for r in cands}
    got = {}
    for p in res.get("picks", []):
        try:
            got[int(p.get("n", 0))] = p
        except (TypeError, ValueError):
            pass
    out, used_ids, used_shoots = [], set(), set()
    for i, tmpl in enumerate(templates, 1):
        p = got.get(i) or {}
        rid = p.get("id")
        conf = float(p.get("confidence") or 0)
        reason = str(p.get("reason") or "").strip()
        row = by_id.get(rid) if rid else None
        if row and (conf < C.PICK_MIN_CONFIDENCE or rid in used_ids
                    or (i == 1 and row.get("eligible") != "Yes")
                    or (C.REUSE_ONE_PER_SHOOT and _shoot_of(row) in used_shoots)):
            reason = (f"picked {rid} at {conf:.2f} but " +
                      ("below floor" if conf < C.PICK_MIN_CONFIDENCE else
                       "already used in this post" if rid in used_ids else
                       "not cover-eligible" if i == 1 else "same shoot as another slide")
                      + " - generating")
            row = None
        if row:
            used_ids.add(rid); used_shoots.add(_shoot_of(row))
        out.append((row, conf, reason))
    return out


def _gen_from_brief(brief, ttype):
    scene = (brief or "").strip()
    if not scene:
        return _gen_prompt(ttype, "")
    return PROMPT_BASE.format(scene=scene.rstrip(".") + ".")


def build_plan(topic, lib_rows, taken_covers, cover_template=None):
    """Returns (sources[7], mix_summary). Fully visible strings, editable in the sheet."""
    ttype = topic["type"]
    plan = list(DEFAULT_PLANS.get(ttype, DEFAULT_PLANS["Fabric Education"]))
    if cover_template:
        plan[0] = cover_template
    texts = [s for s in topic["slides"] if s.strip()]
    templates = _fit_plan(plan, len(texts))
    briefs = [b for b in (topic.get("briefs") or [])]
    if any(b.strip() for b in briefs):
        picks = pick_images(topic, templates, briefs, lib_rows, set(taken_covers))
        if picks is not None:
            sources = []
            for i, (tmpl, (row, conf, reason)) in enumerate(zip(templates, picks)):
                if tmpl not in PHOTO_TEMPLATES and tmpl not in COVER_TEMPLATES:
                    sources.append(f"[{tmpl}] FLAT {C.FLAT_BACKGROUNDS[i % len(C.FLAT_BACKGROUNDS)]}")
                elif row:
                    sources.append(f"[{tmpl}] REUSE {row['id']} ({conf:.2f}: {reason[:110]})")
                    taken_covers.add(row["id"])
                else:
                    sources.append(f"[{tmpl}] GEN: " + _gen_from_brief(briefs[i] if i < len(briefs) else "", ttype))
            sources += [""] * (7 - len(sources))
            n_reuse = sum(1 for x in sources if "REUSE" in x)
            n_gen = sum(1 for x in sources if "GEN:" in x)
            n_flat = sum(1 for x in sources if "FLAT" in x)
            return sources, f"{n_reuse} reuse - {n_gen} gen - {n_flat} flat (picker)"
    # no briefs (or the picker call failed): v1.8 keyword matcher
    sources, used_ids, used_shoots = [], [], set()
    text_i = 0
    flats = C.FLAT_BACKGROUNDS
    for i, tmpl in enumerate(templates):
        if i == 0:
            # cover: reuse only a cover-eligible image, else generate
            hit = _pick(_keywords(ttype), lib_rows,
                        list(used_ids) + list(taken_covers), used_shoots, need_cover=True,
                        slide_text=texts[0] if texts else "")
            if hit:
                sources.append(f"[{tmpl}] REUSE {hit['id']} ({hit['subject'][:60]})")
                used_ids.append(hit["id"]); taken_covers.add(hit["id"])
                used_shoots.add(_shoot_of(hit))
            else:
                sources.append(f"[{tmpl}] GEN: " + _gen_prompt(ttype, texts[0] if texts else ""))
        elif tmpl in PHOTO_TEMPLATES:
            stext = texts[text_i] if (tmpl not in NO_TEXT_TEMPLATES and text_i < len(texts)) else ""
            hit = _pick(_keywords(ttype), lib_rows, list(used_ids) + list(taken_covers),
                        used_shoots, slide_text=stext)
            if hit:
                sources.append(f"[{tmpl}] REUSE {hit['id']} ({hit['subject'][:60]})")
                used_ids.append(hit["id"]); taken_covers.add(hit["id"])
                used_shoots.add(_shoot_of(hit))
            else:
                sources.append(f"[{tmpl}] GEN: " + _gen_prompt(ttype, stext))
        else:
            sources.append(f"[{tmpl}] FLAT {flats[i % len(flats)]}")
        if tmpl not in NO_TEXT_TEMPLATES:
            text_i += 1
    sources += [""] * (7 - len(sources))
    n_reuse = sum(1 for s in sources if "REUSE" in s)
    n_gen = sum(1 for s in sources if "GEN:" in s)
    n_flat = sum(1 for s in sources if "FLAT" in s)
    mix = f"{n_reuse} reuse - {n_gen} gen - {n_flat} flat"
    return sources, mix


def _next_cover(prev, i, topic_type=None):
    """Walk the right cycle by POSITION (not by name - cover_plain appears
    twice), skipping a slot that would repeat the previous post's cover.
    Photo-essay types use their own cycle. Returns (template, next_index)."""
    cycle = _cycle_for(topic_type)
    n = len(cycle)
    for step in range(n):
        tmpl = cycle[(i + step) % n]
        if tmpl != prev:
            return tmpl, (i + step + 1) % n
    return cycle[i % n], (i + 1) % n


def live_reuse_ids(existing_rows, skip_num=None):
    """Every library id already reused by a LIVE queue row (any slide, not just
    the cover). A new row may not repeat any of them: #12 and #16 went out with
    three of five photos in common. skip_num: leave one row out (replanning it)."""
    ids = set()
    for r in existing_rows[1:]:
        r = (r + [""] * 19)[:19]
        if "SUPERSEDED" in (r[18] or "").upper():
            continue
        if skip_num is not None and str(r[0]) == str(skip_num):
            continue
        for cell in r[6:13]:
            ids.update(re.findall(r"REUSE (IMG-\d+)", cell or ""))
    return ids


def replan(number):
    """Rebuild one existing queue row's image plan in place and send it back to
    the render gate. For when the plan itself was wrong, not one slide."""
    qws = S.tab(C.TAB_QUEUE)
    existing_rows = qws.get_all_values()
    q = next((x for x in S.queue_rows() if str(x["num"]) == str(number)), None)
    if not q:
        return f"#{number} not found"
    topic = next((t for t in S.topics_rows() if str(t["num"]) == str(q["topic"])), None)
    if not topic:
        return f"#{number}: topic {q['topic']} not found"
    m = re.match(r"\[(\w+)\]", (q["sources"][0] or "").strip())
    cover = m.group(1) if m and m.group(1) in COVER_TEMPLATES else None
    sources, mix = build_plan(topic, L.library_rows(),
                              live_reuse_ids(existing_rows, skip_num=number),
                              cover_template=cover)
    qws.update(values=[sources + [mix]], range_name=f"G{q['row']}:N{q['row']}")
    qws.update_acell(f"Q{q['row']}", "")
    # the old caption's alt texts describe images that no longer exist
    cws = S.tab("Generated Caption")
    for i, r in enumerate(cws.get_all_values(), start=1):
        if r and str(r[0]) == str(number):
            cws.delete_rows(i)
            break
    st = next((x for x in S.status_rows() if str(x["num"]) == str(number)), None)
    if st:
        S.tab(C.TAB_STATUS).batch_update([
            {"range": f"E{st['row']}", "values": [[""]]},
            {"range": f"F{st['row']}:G{st['row']}", "values": [["", ""]]},
            {"range": f"H{st['row']}:K{st['row']}", "values": [["Not Available", "", "", ""]]},
        ])
        S.add_remark(st["row"], "PLAN", f"re-planned with slide-level matching ({mix}); back to the render gate")
    return f"#{number} re-planned: {mix}"


def queued_topic_nums(existing_rows):
    """Topic #s that already have a LIVE queue row. Rows whose Notes (col S)
    contain SUPERSEDED are ignored, so their topic can be planned again."""
    out = set()
    for r in existing_rows[1:]:
        r = (r + [""] * 19)[:19]
        if "SUPERSEDED" in (r[18] or "").upper():
            continue
        out.add(r[3])
    return out


def rotation_state(existing_rows):
    """(last_cover, cover_index) derived from the live queue rows."""
    import re as _re
    last_cover, live = None, 0
    for r in existing_rows[1:]:
        r = (r + [""] * 19)[:19]
        if "SUPERSEDED" in (r[18] or "").upper():
            continue
        live += 1
        t = _re.match(r"\[(\w+)\]", (r[6] or "").strip())
        if t and t.group(1) in COVER_TEMPLATES:
            last_cover = t.group(1)
    return last_cover, live % len(COVER_CYCLE)


def cover_from_remark(remark):
    import re as _re
    m = _re.findall(r"cover=(\w+)", remark or "")
    return m[-1] if m and m[-1] in COVER_TEMPLATES else None


def sync():
    """Create queue+status rows for Approved topics that have slide text and no
    live queue row yet. All reads happen once up front; all writes are batched."""
    qws = S.tab(C.TAB_QUEUE)
    existing_rows = qws.get_all_values()
    queued_topics = queued_topic_nums(existing_rows)
    lib_rows = L.library_rows()
    taken_covers = live_reuse_ids(existing_rows)
    last_cover, cover_i = rotation_state(existing_rows)
    now = datetime.datetime.now()
    new_q, new_s = [], []
    num = len(existing_rows) - 1  # data rows so far (superseded rows keep their numbers)
    for t in S.topics_rows():
        if t["status"] != "Approved" or not t["num"] or t["num"] in queued_topics:
            continue
        if t["type"] in C.PARKED_TYPES:
            continue  # Marcus parked this type: still TBD / prototyping
        if not any(s.strip() for s in t["slides"]):
            continue  # no slide text yet — words come first (writer_edu drafts them)
        chosen = cover_from_remark(t["remark"])
        if chosen:
            cover = chosen
        else:
            cover, cover_i = _next_cover(last_cover, cover_i, t["type"])
        last_cover = cover
        sources, mix = build_plan(t, lib_rows, taken_covers, cover_template=cover)
        num += 1
        new_q.append([num, now.year, now.strftime("%m. %B"), t["num"], t["type"],
                      SERIES_FOR.get(t["type"], "")]
                     + sources + [mix, "", "", "", "", ""])
        remark = (f"[{S.now_hkt()}] PLAN: image plan drafted ({mix}), cover={cover} — "
                  f"review Slide Source cols + the words in Post Topic, then set D=Approved")
        new_s.append(["", num, t["num"], "Drafted", "", "", "", "Not Available", "", "", "", "", "", remark, ""])
    if new_q:
        qws.append_rows(new_q, value_input_option="RAW")
        first = new_s[0][1]
        srow = C.STATUS_HEADER_ROW + first
        S.tab(C.TAB_STATUS).update(values=new_s, range_name=f"A{srow}:O{srow + len(new_s) - 1}")
    return f"{len(new_q)} new plan(s) drafted"
