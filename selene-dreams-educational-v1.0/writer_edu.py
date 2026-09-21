# =============================================================================
# writer_edu.py — drafts an educational carousel's slide copy on Approved
# VERSION 1.4 — 2026-09-16
# CHANGELOG
#   1.4  2026-09-16  {taste_brief}: the cross-lane taste brief (v3.0
#                    taste_brief.py, on sys.path) goes into writer_edu.md v6.
#                    Fail-open placeholder.
#   1.3  2026-09-09  Skips PARKED_TYPES (Inspirational).
#   1.2  2026-09-09  TELL INFRASTRUCTURE FAILURES APART FROM COPY FAILURES. The
#                    redraft batch hit the Claude CLI's session limit and logged
#                    "WRITER: FLAGGED" on three topics - the same words a genuine
#                    cap overflow writes. Reading the sheet later, nobody could
#                    tell "this copy is bad" from "we ran out of quota", and a
#                    retry would look like a rewrite of working copy. draft() now
#                    returns a reason kind, and the caller writes BLOCKED (retry
#                    as is) or FLAGGED (needs a human) accordingly.
#   1.1  2026-09-09  Feeds RECENT COPY (what other topics in the lane already
#                    say) into the prompt, the way the caption runner feeds
#                    recent styles. The first nine drafts built three separate
#                    posts on the same hollow-fibre claim because each draft was
#                    written blind to the others. Also adds --redraft, which
#                    clears a topic's Slide cells and drafts it again regardless
#                    of Status, so a prompt fix can be re-run on existing rows.
#   1.0  2026-09-09  First release. Marcus's call: the moment a topic is
#                    Approved, the runner drafts every slide's title + description
#                    so the D gate always shows him words AND plan together and he
#                    only ever edits, never starts from blank.
#                    - Same mechanism as the image lane's caption runner: the
#                      Claude Code CLI headlessly, through v3.0's claude_client
#                      (IMPORTED, not copied), with a versioned prompt file.
#                    - Validation is the RENDERER'S OWN measurement (_measure):
#                      the same wrap, the same fonts, the same caps. Copy that
#                      passes here cannot fail at render time.
#                    - Overflow -> the exact problem is fed back for up to
#                      WRITER_MAX_ROUNDS rewrites, then the row is FLAGGED in its
#                      remark and left blank so plan_edu does not proceed.
#                    - Chooses the cover template with the same rotation plan_edu
#                      uses and records it in the topic remark ("cover=...") so
#                      the two stages cannot disagree about which caps applied.
#                    - Product facts come only from prompts/claims_edu.md; any
#                      general-knowledge line the model uses is surfaced in the
#                      remark for Marcus.
# =============================================================================
import os, re, json, tempfile, shutil
import config_edu as C
import sheets_edu as S
from templates_edu import (TEMPLATES, DEFAULT_PLANS, SERIES_FOR, PHOTO_ESSAY_TYPES,
                           NO_TEXT_TEMPLATES)
import plan_edu

# v3.0 modules, imported via C.V3_DIR on sys.path
from claude_client import invoke_claude_json

# draft() first return value: True = drafted, False = the copy failed on its own
# merits, BLOCKED = the run never happened (quota, auth, timeout) so retry as is.
BLOCKED = "BLOCKED"

WRITER_SCHEMA = {
    "slides":        {"type": "list", "required": True, "min_len": 1},
    "generalClaims": {"type": "list", "required": False},
    "remark":        {"type": "str",  "required": False},
}

# Post Topic "Topics" tab: A # · B Type · C Desc · D-J Slide 1-7 · K Status · L url · M Remark
SLIDE_COLS = ["D", "E", "F", "G", "H", "I", "J"]
REMARK_COL = "M"


from log_edu import log


# --- what the writer has to fill ---------------------------------------------

def text_slides(plan):
    """[(slide_no, template)] for the slides that take copy from the sheet."""
    return [(i + 1, t) for i, t in enumerate(plan) if t not in NO_TEXT_TEMPLATES]


def slide_spec(plan):
    """Human-readable cap sheet for the prompt, one line per text slide."""
    lines = []
    for n, tmpl in text_slides(plan):
        zones = TEMPLATES[tmpl]["zones"]
        parts = []
        for z in zones:
            opt = " (optional)" if z.get("optional") else ""
            parts.append(f"{z['name']} max {z['max_chars']} chars / {z.get('max_lines', 1)} line(s){opt}")
        lines.append(f"  slide {n} [{tmpl}]: " + " · ".join(parts))
    return "\n".join(lines)


def validate(slides, plan):
    """Run the renderer's own measurement. Returns a list of problems."""
    from PIL import Image, ImageDraw
    from renderer_edu import _measure, OverflowError2
    d = ImageDraw.Draw(Image.new("RGB", (C.CANVAS_W, C.CANVAS_H)))
    problems = []
    want = text_slides(plan)
    if len(slides) != len(want):
        return [f"expected {len(want)} slides, got {len(slides)}"]
    for (n, tmpl), sl in zip(want, slides):
        spec = TEMPLATES[tmpl]
        texts = {"title": str(sl.get("title", "")).strip(),
                 "desc": str(sl.get("desc", "")).strip()}
        for k, v in texts.items():
            if "—" in v or "–" in v or " - " in v:
                problems.append(f"slide {n} {k}: dash punctuation is banned")
            if "!" in v:
                problems.append(f"slide {n} {k}: no exclamation marks")
        stack = spec.get("stack")
        box_w = stack["w"] * C.CANVAS_W if stack else C.CANVAS_W - 2 * C.MARGIN
        try:
            _measure(d, spec, texts, C.CANVAS_W, box_w)
        except OverflowError2 as e:
            problems.append(f"slide {n} [{tmpl}]: {e}")
    return problems


def cell_text(sl):
    t = str(sl.get("title", "")).strip()
    dsc = str(sl.get("desc", "")).strip()
    return f"{t} | {dsc}" if dsc else t


# --- one topic ---------------------------------------------------------------

def recent_copy(exclude_num=None, limit=6):
    """What other topics in this lane already say, newest first. Keeps the
    writer from building three posts on the same claim."""
    out = []
    for t in reversed(S.topics_rows()):
        if str(t["num"]) == str(exclude_num):
            continue
        slides = [s for s in t["slides"] if s.strip()]
        if not slides:
            continue
        out.append(f"  {t['type']} — " + " / ".join(s.strip() for s in slides))
        if len(out) >= limit:
            break
    return "\n".join(out) if out else "  (nothing drafted yet)"


def _taste_brief():
    try:
        import taste_brief
        return taste_brief.brief_block("writer_edu")
    except Exception:
        return "(taste brief unavailable this run)"


def draft(topic, cover_template):
    """Returns (ok, slides_or_message, general_claims, remark)."""
    ttype = topic["type"]
    plan = list(DEFAULT_PLANS.get(ttype, DEFAULT_PLANS["Fabric Education"]))
    plan[0] = cover_template
    want = text_slides(plan)
    with open(C.CLAIMS_PATH) as f:
        claims = f.read()
    template, version = _load_edu_prompt("writer_edu")
    workdir = tempfile.mkdtemp(prefix=f"selene_writer_{topic['num']}_")
    try:
        out_path = os.path.join(workdir, "slides.json")
        base = template.format(
            topic_type=ttype, series=SERIES_FOR.get(ttype, ttype),
            topic_desc=topic["desc"] or "(no description given)",
            cover_template=cover_template, slide_spec=slide_spec(plan),
            n_slides=len(want), last_n=want[-1][0], claims=claims,
            recent_copy=recent_copy(exclude_num=topic["num"]), out_path=out_path,
            taste_brief=_taste_brief())
        prompt = base
        for rnd in range(1, C.WRITER_MAX_ROUNDS + 2):
            ok, result = invoke_claude_json(prompt, workdir, out_path, schema=WRITER_SCHEMA,
                                            stage="writer_edu", timeout=C.WRITER_TIMEOUT)
            if not ok:
                # Infrastructure, not judgement: quota, auth, a missing CLI, a
                # timeout. The copy was never assessed, so this retries as is.
                return BLOCKED, result, [], ""
            slides = result.get("slides") or []
            problems = validate(slides, plan)
            if not problems:
                return True, slides, [str(x) for x in (result.get("generalClaims") or [])], \
                       str(result.get("remark") or "").strip()
            if rnd > C.WRITER_MAX_ROUNDS:
                return False, "still over cap after %d rewrites: %s" % (
                    C.WRITER_MAX_ROUNDS, "; ".join(problems[:4])), [], ""   # judgement: needs a human
            log(f"  writer round {rnd}: {len(problems)} problem(s), asking for a rewrite")
            prompt = (base + "\n\n---\nYOUR PREVIOUS DRAFT BROKE THESE RULES:\n- "
                      + "\n- ".join(problems)
                      + f"\nRewrite ONLY what is needed to fix them, keep everything else, "
                        f"and write the complete corrected JSON to {out_path} again.")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _load_edu_prompt(name):
    """Same contract as claude_client.load_prompt but reads THIS flow's prompts/."""
    path = os.path.join(C.PROMPT_DIR, name + ".md")
    with open(path) as f:
        text = f.read()
    m = re.search(r"<!--\s*VERSION:\s*([^\s>]+)\s*-->", text)
    return text, (m.group(1) if m else "unversioned")


# --- the sync ----------------------------------------------------------------

def sync():
    """Draft copy for every Approved topic whose Slide cells are all empty.
    Chooses the cover with the same rotation plan_edu uses and records it in the
    topic's remark so plan_edu honours it."""
    ws = S.topic_sheet().worksheet(C.TAB_TOPICS)
    topics = S.topics_rows()
    existing_q = S.tab(C.TAB_QUEUE).get_all_values()
    queued = plan_edu.queued_topic_nums(existing_q)
    last_cover, cover_i = plan_edu.rotation_state(existing_q)
    done, flagged, blocked = 0, 0, 0
    for t in topics:
        if t["status"] != "Approved" or not t["num"] or t["num"] in queued:
            continue
        if t["type"] in C.PARKED_TYPES:
            continue  # Marcus parked this type: still TBD / prototyping
        if any(s.strip() for s in t["slides"]):
            continue                              # Marcus (or a past run) already wrote it
        r = t["remark"] or ""
        if "WRITER: FLAGGED" in r and r.rfind("WRITER: FLAGGED") > r.rfind("WRITER: BLOCKED"):
            continue                              # flagged on merit; wait for a human edit
        cover, cover_i = plan_edu._next_cover(last_cover, cover_i, t["type"])
        log(f"writer: topic #{t['num']} ({t['type']}) -> {cover}")
        ok, slides, general, remark = draft(t, cover)
        stamp = S.now_hkt()
        if ok is BLOCKED:
            _remark(ws, t["row"], t["remark"],
                    f"[{stamp}] WRITER: BLOCKED cover={cover} · {slides} · "
                    f"copy never assessed, safe to retry unchanged")
            blocked += 1
            continue
        if not ok:
            _remark(ws, t["row"], t["remark"],
                    f"[{stamp}] WRITER: FLAGGED cover={cover} · {slides}")
            flagged += 1
            continue
        # write D..J in one batch
        cells = [cell_text(sl) for sl in slides] + [""] * (7 - len(slides))
        ws.update(values=[cells], range_name=f"D{t['row']}:J{t['row']}")
        note = f"[{stamp}] WRITER: cover={cover} · drafted {len(slides)} slide(s)"
        if general:
            note += " · GENERAL CLAIMS (verify): " + " / ".join(general)
        if remark:
            note += " · " + remark
        _remark(ws, t["row"], t["remark"], note)
        last_cover = cover
        done += 1
    return f"{done} drafted, {flagged} flagged, {blocked} blocked"


def _remark(ws, row, current, entry):
    cur = (current or "").strip()
    ws.update_acell(f"{REMARK_COL}{row}", (cur + " | " + entry) if cur else entry)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="draft one topic to stdout, write nothing")
    ap.add_argument("--redraft", action="store_true",
                    help="clear and redraft --topic regardless of Status (for prompt fixes)")
    ap.add_argument("--topic", help="topic # to draft")
    a = ap.parse_args()
    if a.redraft:
        t = next((x for x in S.topics_rows() if x["num"] == str(a.topic)), None)
        if not t:
            raise SystemExit(f"topic {a.topic} not found")
        ws = S.topic_sheet().worksheet(C.TAB_TOPICS)
        existing_q = S.tab(C.TAB_QUEUE).get_all_values()
        last, i = plan_edu.rotation_state(existing_q)
        cover = plan_edu.cover_from_remark(t["remark"]) or plan_edu._next_cover(last, i, t["type"])[0]
        log(f"redraft: topic #{t['num']} ({t['type']}) -> {cover}")
        ok, slides, general, remark = draft(t, cover)
        stamp = S.now_hkt()
        if not ok:
            _remark(ws, t["row"], t["remark"], f"[{stamp}] WRITER: FLAGGED cover={cover} · {slides}")
            raise SystemExit(f"FLAGGED: {slides}")
        cells = [cell_text(sl) for sl in slides] + [""] * (7 - len(slides))
        ws.update(values=[cells], range_name=f"D{t['row']}:J{t['row']}")
        note = f"[{stamp}] WRITER v1.1: cover={cover} · redrafted {len(slides)} slide(s)"
        if general:
            note += " · GENERAL CLAIMS (verify): " + " / ".join(general)
        if remark:
            note += " · " + remark
        _remark(ws, t["row"], t["remark"], note)
        for n, sl in enumerate(slides, 1):
            print(f"  {n}. {cell_text(sl)}")
        print("general claims:", general)
    elif a.dry_run:
        t = next((x for x in S.topics_rows() if x["num"] == str(a.topic)), None)
        if not t:
            raise SystemExit(f"topic {a.topic} not found")
        existing_q = S.tab(C.TAB_QUEUE).get_all_values()
        last, i = plan_edu.rotation_state(existing_q)
        cover, _ = plan_edu._next_cover(last, i, t["type"])
        ok, slides, general, remark = draft(t, cover)
        print("cover:", cover, "| ok:", ok)
        if ok:
            for n, sl in enumerate(slides, 1):
                print(f"  {n}. {cell_text(sl)}")
            print("general claims:", general); print("remark:", remark)
        else:
            print("FLAGGED:", slides)
    else:
        print(sync())
