# =============================================================================
# reroll_edu.py — regenerate ONE slide from Marcus's comment on the image
# VERSION 1.1 — 2026-09-10
# CHANGELOG
#   1.1  2026-09-10  COLUMN-O GRAMMAR for the candidate picker (Marcus, 2026-09-10).
#                    Three kinds of reply, separated by "|" or new lines:
#                        3B                 use candidate B for slide 3
#                        5 reroll: comment  regenerate slide 5 from its prompt + comment
#                        5 new: idea        regenerate slide 5 from a fresh idea
#                    ("reroll 5: comment" still works.) A REUSE slide rerolls
#                    from the slide's visual brief, not the topic-type scene.
#                    Every regenerated image is registered as a new candidate
#                    (col T, next letter, chosen) and appended to the Image
#                    Library with the brief as its description.
#   1.0  2026-09-09  First release. Marcus's chosen picker model (2026-09-09):
#                    generate first, show him the prompt that was actually used,
#                    he comments, and the comment plus the ORIGINAL prompt make a
#                    revised prompt that regenerates only that slide.
#                    HOW HE ASKS: put a line in Generation Status col O
#                    (User Remark(s)):
#                        reroll 3: too dark, want morning light
#                    Several are fine, separated by "|". A REUSE slide can be
#                    rerolled too - it converts to a generation seeded from the
#                    topic's scene plus his comment.
#                    The revised prompt is WRITTEN BACK into the Slide Source
#                    cell, so the next reroll builds on it and the sheet always
#                    shows the prompt that actually made the picture.
#                    Only the named slide is regenerated and re-uploaded; the
#                    other slides are untouched and cost nothing.
# =============================================================================
import os, re, io, json, tempfile, shutil, datetime, argparse
import config_edu as C
import sheets_edu as S
import library_edu as L
import renderer_edu as R
import render_runner_edu as RR
from templates_edu import SERIES_FOR
from log_edu import log
from claude_client import invoke_claude_json

SCHEMA = {"prompt": {"type": "str", "min_len": 20}, "changed": {"type": "str", "required": False}}
SLIDE_SRC_COLS = ["G", "H", "I", "J", "K", "L", "M"]   # Generation Queue slide 1-7 source


def _prompt_file():
    with open(os.path.join(C.PROMPT_DIR, "reroll_edu.md")) as f:
        text = f.read()
    m = re.search(r"<!--\s*VERSION:\s*([^\s>]+)\s*-->", text)
    return text, (m.group(1) if m else "unversioned")


def parse_requests(user_remark):
    """Column O -> [(slide_no, kind, payload)], kind in choose / reroll / new.
    '3B | 5 reroll: too dark | 2 new: a hand on the sheet'
      -> [(3,'choose','B'), (5,'reroll','too dark'), (2,'new','a hand on the sheet')]"""
    out = []
    text = user_remark or ""
    if text.lstrip().startswith("[done"):
        return out
    for part in re.split(r"\||\n", text):
        p = part.strip()
        if not p:
            continue
        m = re.match(r"(?:slide\s*)?(\d)\s*([A-Da-d])$", p)
        if m:
            out.append((int(m.group(1)), "choose", m.group(2).upper())); continue
        m = re.match(r"(?:reroll\s*(\d)|(\d)\s*reroll)\s*:\s*(.+)$", p, re.I)
        if m:
            out.append((int(m.group(1) or m.group(2)), "reroll", m.group(3).strip())); continue
        m = re.match(r"(?:new\s*(\d)|(\d)\s*new)\s*:\s*(.+)$", p, re.I)
        if m:
            out.append((int(m.group(1) or m.group(2)), "new", m.group(3).strip())); continue
    return out


def original_prompt(source_cell, topic_type):
    """The GEN prompt in the cell, or a seed if the slide was a REUSE."""
    parsed = RR._parse_source(source_cell)
    if not parsed:
        return None, None
    tmpl, kind, payload = parsed
    if kind == "GEN":
        return tmpl, payload
    import plan_edu
    scene = plan_edu.SCENES.get(topic_type, plan_edu.SCENES["Fabric Education"])
    return tmpl, plan_edu.PROMPT_BASE.format(scene=scene)


def _brief_for(topic, slide_no):
    briefs = (topic or {}).get("briefs") or []
    return briefs[slide_no - 1].strip() if slide_no - 1 < len(briefs) else ""


def _candidates_of(q):
    try:
        return json.loads(q.get("candidates") or "{}")
    except Exception:
        return {}


def _row_folder(number):
    root = L.find_folder(C.GENERATED_IMAGES_FOLDER_NAME)
    return L.ensure_folder(f"Row {number}", L.ensure_folder(C.EDU_OUTPUT_SUBFOLDER, root))


def _swap_slide(q, st, number, slide_no, tmpl, bg, slide_text, workdir, remark):
    """Re-render one slide over bg, upload, replace its URL, K back to Review."""
    texts = RR._zone_texts(tmpl, slide_text, slide_no)
    img = R.render_slide(tmpl, texts, background=bg)
    local = os.path.join(workdir, f"row{number}_slide{slide_no}.jpg")
    R.save_jpeg(img, local)
    fid, _ = L.upload_jpeg(local, os.path.basename(local), _row_folder(number))
    urls = [u for u in (q["urls"] or "").splitlines() if u.strip()]
    while len(urls) < slide_no:
        urls.append("")
    urls[slide_no - 1] = f"https://drive.google.com/uc?id={fid}"
    S.tab(C.TAB_QUEUE).update_acell(f"Q{q['row']}", "\n".join(urls))
    S.add_remark(st["row"], "REROLL", remark)


def choose_candidate(number, slide_no, label):
    """'3B': put candidate B under slide 3's words."""
    q = next((x for x in S.queue_rows() if str(x["num"]) == str(number)), None)
    st = next((x for x in S.status_rows() if str(x["num"]) == str(number)), None)
    if not q or not st:
        return False, f"#{number}: row not found"
    cands = _candidates_of(q)
    entry = cands.get(str(slide_no)) or {}
    loc = entry.get(label)
    if not loc:
        have = [k for k in entry if len(k) == 1]
        return False, f"#{number} slide {slide_no}: no candidate {label} (have {', '.join(have) or 'none'})"
    parsed = RR._parse_source(q["sources"][slide_no - 1])
    tmpl = parsed[0] if parsed else "bubble_card"
    topic = next((t for t in S.topics_rows() if str(t["num"]) == str(q["topic"])), None)
    slide_text = (topic["slides"][slide_no - 1].strip() if topic else "")
    workdir = tempfile.mkdtemp(prefix=f"selene_choose_{number}_{slide_no}_")
    try:
        from PIL import Image
        bg = Image.open(io.BytesIO(L.download_image(loc)))
        _swap_slide(q, st, number, slide_no, tmpl, bg, slide_text, workdir,
                    f"slide {slide_no}: candidate {label} chosen")
        entry["chosen"] = label
        cands[str(slide_no)] = entry
        S.tab(C.TAB_QUEUE).update_acell(f"T{q['row']}", json.dumps(cands))
        return True, f"#{number} slide {slide_no}: candidate {label} in place"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def reroll_slide(number, slide_no, comment, dry_run=False, kind="reroll"):
    """Revise one slide's prompt (kind=reroll) or start from a fresh idea
    (kind=new), regenerate it, re-render, replace its URL."""
    q = next((x for x in S.queue_rows() if str(x["num"]) == str(number)), None)
    st = next((x for x in S.status_rows() if str(x["num"]) == str(number)), None)
    if not q or not st:
        return False, f"#{number}: row not found"
    if not 1 <= slide_no <= 7:
        return False, f"#{number}: slide {slide_no} out of range"
    cell = q["sources"][slide_no - 1]
    if not cell.strip():
        return False, f"#{number}: slide {slide_no} has no source"
    topic = next((t for t in S.topics_rows() if str(t["num"]) == str(q["topic"])), None)
    ttype = q["type"]
    tmpl, orig = original_prompt(cell, ttype)
    if not orig:
        return False, f"#{number}: could not read slide {slide_no}'s source cell"
    brief = _brief_for(topic, slide_no)
    if "REUSE" in cell and brief:
        import plan_edu
        orig = plan_edu.PROMPT_BASE.format(scene=brief.rstrip(".") + ".")   # the brief, not the type scene

    slide_text = (topic["slides"][slide_no - 1].strip() if topic else "") or "(no words on this slide)"
    workdir = tempfile.mkdtemp(prefix=f"selene_reroll_{number}_{slide_no}_")
    try:
        out_path = os.path.join(workdir, "prompt.json")
        if kind == "new":
            import plan_edu
            new_prompt = plan_edu.PROMPT_BASE.format(scene=comment.strip().rstrip(".") + ".")
            changed = "fresh idea from Marcus"
        else:
            tpl, ver = _prompt_file()
            ok, res = invoke_claude_json(
                tpl.format(original_prompt=orig, comment=comment, slide_no=slide_no,
                           topic_type=ttype, series=SERIES_FOR.get(ttype, ttype),
                           slide_text=slide_text, out_path=out_path),
                workdir, out_path, schema=SCHEMA, stage="reroll_edu", timeout=C.REROLL_TIMEOUT)
            if not ok:
                return False, f"prompt revision failed: {res}"
            new_prompt = res["prompt"].strip()
            changed = str(res.get("changed", "")).strip()
        log(f"  #{number} slide {slide_no}: {changed or 'prompt revised'}")
        if dry_run:
            print("\n--- ORIGINAL ---\n" + orig + "\n\n--- REVISED ---\n" + new_prompt)
            return True, "(dry run, nothing generated)"

        bg = RR._gen_image(new_prompt)
        # register as the next candidate letter, chosen, and in the library
        cands = _candidates_of(q)
        entry = cands.get(str(slide_no)) or {}
        label = chr(65 + len([k for k in entry if len(k) == 1]))
        ids = RR._register_candidates(number, slide_no, brief or new_prompt, [bg],
                                      _row_folder(number), workdir)
        # _register_candidates names the first image "A"; re-label to the next letter
        entry[label] = ids["A"]; entry["chosen"] = label; entry["prompt"] = new_prompt
        cands[str(slide_no)] = entry
        _swap_slide(q, st, number, slide_no, tmpl, bg, slide_text if topic else "", workdir,
                    f"slide {slide_no} regenerated as candidate {label} · {changed or 'prompt revised'} · "
                    f"asked for: {comment[:80]}")
        qws = S.tab(C.TAB_QUEUE)
        qws.update_acell(f"T{q['row']}", json.dumps(cands))
        # the sheet must always show the prompt that actually made the picture
        qws.update_acell(f"{SLIDE_SRC_COLS[slide_no - 1]}{q['row']}", f"[{tmpl}] GEN: {new_prompt}")
        return True, f"#{number} slide {slide_no} rerolled (candidate {label})"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def run_pending(dry_run=False):
    """Any row whose User Remark(s) carries an unactioned 'reroll N: ...'."""
    n = 0
    ws = S.tab(C.TAB_STATUS)
    for st in S.status_rows():
        remark = ws.acell(f"O{st['row']}").value or ""
        reqs = parse_requests(remark)
        if not reqs:
            continue
        for slide_no, kind, payload in reqs:
            if kind == "choose":
                ok, msg = choose_candidate(st["num"], slide_no, payload)
            else:
                ok, msg = reroll_slide(st["num"], slide_no, payload, dry_run=dry_run, kind=kind)
            log(f"reroll: {msg}")
            n += 1 if ok else 0
        if not dry_run:
            # clear the request so the next tick does not repeat it, keeping a trace
            ws.update_acell(f"O{st['row']}", f"[done {S.now_hkt()}] " + remark)
            S.set_status(st["row"], "K", C.POST_REVIEW)   # back for another look
    return f"{n} slide(s) rerolled"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--number"); ap.add_argument("--slide", type=int)
    ap.add_argument("--comment"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.number and a.slide and a.comment:
        print(reroll_slide(a.number, a.slide, a.comment, dry_run=a.dry_run))
    else:
        print(run_pending(dry_run=a.dry_run))
