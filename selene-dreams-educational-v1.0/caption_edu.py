# =============================================================================
# caption_edu.py — caption + alt text for a rendered educational carousel
# VERSION 1.3 — 2026-09-16
# CHANGELOG
#   1.3  2026-09-16  {taste_brief} in caption_edu.md v5. Fail-open.
#   1.2  2026-09-10  PHANTOM SLIDE FIX. slide_copy_block listed every Post Topic
#                    slide cell, and a blank trailing cell became "(photo only,
#                    no words)" - so a six-slide render was described to the
#                    model as seven slides, it wrote six alt texts, and the
#                    brand review (correctly) failed it for the missing seventh.
#                    The block is now sliced to the RENDERED slide count, and
#                    only a blank cell INSIDE that count is a wordless slide.
#                    Also enforces the Stage 0 style gate in code: a style other
#                    than One Line / Two Beat is rejected before the review call,
#                    so a prompt regression cannot burn a second Claude call.
#   1.1  2026-09-09  SKIP SUPERSEDED ROWS. run_pending picked up row 9 - the
#                    Aug-28 test render, marked D=Superseded - purely because it
#                    still had E=Done, and burned two Claude calls captioning a
#                    row that will never be published. The words gate now guards
#                    the caption stage too: nothing is captioned unless D is
#                    Approved.
#   1.0  2026-09-09  First release. Runs after E=Done. IMPORTS the image lane's
#                    caption machinery (validator, style rotation log, memory
#                    clone, playbook push, schemas) from v3.0's caption_runner
#                    rather than copying it, so the two lanes cannot drift on
#                    format. The prompt is this flow's own (prompts/caption_edu.md)
#                    and points the model at the image lane's caption.md for the
#                    style register - ONE definition of the seven styles.
#                    Shop pointer = the site name in the body, nothing else
#                    (Marcus, 2026-09-09). Product facts only from claims_edu.md.
#                    Writes the Generated Caption tab (A # · B caption · C-I alt
#                    1-7 · J written date · K remark), sets H=Done + I/J date/time.
# =============================================================================
import os, re, json, tempfile, shutil, datetime
import config_edu as C
import sheets_edu as S
import library_edu as L
from templates_edu import SERIES_FOR

# v3.0 (read-only imports)
from claude_client import invoke_claude_json, week_context
from caption_runner import (validate_caption, read_recent_styles, format_recent_styles,
                            append_caption_log, clone_memory, build_memory_section,
                            push_playbook_entry, CAPTION_SCHEMA, REVIEW_SCHEMA)

V3_CAPTION_MD = os.path.join(C.V3_DIR, "prompts", "caption.md")
MAX_ALTS = 7


from log_edu import log


def _taste_brief():
    try:
        import taste_brief
        return taste_brief.brief_block("caption_edu")
    except Exception:
        return "(taste brief unavailable this run)"


def _prompt(name):
    with open(os.path.join(C.PROMPT_DIR, name + ".md")) as f:
        text = f.read()
    m = re.search(r"<!--\s*VERSION:\s*([^\s>]+)\s*-->", text)
    return text, (m.group(1) if m else "unversioned")


def drive_ids(urls_cell):
    ids = re.findall(r"[?&]id=([A-Za-z0-9_\-]+)", urls_cell or "")
    ids += re.findall(r"/file/d/([A-Za-z0-9_\-]+)", urls_cell or "")
    seen, out = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i); out.append(i)
    return out


EDU_STYLES = ("One Line", "Two Beat")   # register Stage 0: words on slides


def slide_copy_block(topic, n_rendered):
    """One line per RENDERED slide. A blank Post Topic cell past the rendered
    count is not a slide at all; a blank cell inside it is a wordless slide."""
    lines = []
    cells = list(topic["slides"])[:n_rendered]
    cells += [""] * (n_rendered - len(cells))
    for i, s in enumerate(cells, 1):
        s = (s or "").strip()
        lines.append(f"  slide {i}: {s if s else '(photo only, no words)'}")
    return "\n".join(lines)


def _caption_row_exists(ws, number):
    return str(number) in [r[0] for r in ws.get_all_values()[1:] if r]


def caption_row(number, force=False):
    """Caption queue row #number. Returns (ok, message). Writes the sheet itself."""
    q = next((x for x in S.queue_rows() if str(x["num"]) == str(number)), None)
    if not q:
        return False, f"queue row #{number} not found"
    st = next((x for x in S.status_rows() if str(x["num"]) == str(number)), None)
    if not st:
        return False, f"status row #{number} not found"
    if st["words"] != "Approved":
        return False, f"#{number}: words gate is '{st['words'] or 'blank'}', not Approved"
    if st["render"] != "Done":
        return False, f"#{number}: render is '{st['render'] or 'blank'}', not Done"
    if st["caption"] == "Done" and not force:
        return False, f"#{number}: already captioned"
    topic = next((t for t in S.topics_rows() if str(t["num"]) == str(q["topic"])), None)
    if not topic:
        return False, f"topic {q['topic']} not found in Post Topic"
    ids = drive_ids(q["urls"])
    if not ids:
        return False, f"#{number}: no image URLs on the queue row"

    cap_ws = S.tab(C.TAB_CAPTION)
    if _caption_row_exists(cap_ws, number) and not force:
        return False, f"#{number}: Generated Caption already has a row (delete it to regenerate)"

    S.set_status(st["row"], "H", "Processing")
    workdir = tempfile.mkdtemp(prefix=f"selene_capedu_{number}_")
    try:
        img_dir = os.path.join(workdir, "slides"); os.makedirs(img_dir)
        for i, fid in enumerate(ids, 1):
            with open(os.path.join(img_dir, f"slide_{i:02d}.jpg"), "wb") as f:
                f.write(L.download_image(f"drive:{fid}"))
        mem_dir = clone_memory(workdir)
        with open(C.CLAIMS_PATH) as f:
            claims = f.read()
        ttype = topic["type"]; series = SERIES_FOR.get(ttype, ttype)
        common = dict(topic_type=ttype, series=series,
                      topic_desc=topic["desc"] or "(no description)",
                      slide_copy=slide_copy_block(topic, len(ids)), n_images=len(ids),
                      style_register_path=V3_CAPTION_MD, site_url=C.SITE_URL, claims=claims)

        # --- write ---
        tpl, cap_ver = _prompt("caption_edu")
        out_path = os.path.join(workdir, "caption.json")
        prompt = tpl.format(img_dir=img_dir, week_context=week_context(mem_dir),
                            recent_styles=format_recent_styles(read_recent_styles()),
                            memory_section=build_memory_section(mem_dir),
                            taste_brief=_taste_brief(),
                            out_path=out_path, **common)
        log(f"  caption #{number}: invoking Claude ({cap_ver})")
        ok, res = invoke_claude_json(prompt, workdir, out_path, schema=CAPTION_SCHEMA,
                                     stage="caption", timeout=C.CAPTION_TIMEOUT)
        if not ok:
            return _fail(st, number, res)
        caption = str(res.get("caption", "")).strip()
        style = str(res.get("style", "")).strip()
        alts = [str(a) for a in (res.get("altTexts") or [])]
        if style not in EDU_STYLES:
            return _fail(st, number, f"style '{style or 'none'}' is not eligible for a words-on-slides carousel (One Line or Two Beat only)")
        okf, why = validate_caption(caption, style)
        if not okf:
            return _fail(st, number, f"caption rejected ({style or 'no style'}): {why}")
        if len(alts) != len(ids):
            return _fail(st, number, f"expected {len(ids)} alt texts, got {len(alts)}")
        if caption.count(C.SITE_URL) != 1:
            return _fail(st, number, f"site name must appear exactly once, found {caption.count(C.SITE_URL)}")

        # --- review ---
        rtpl, rev_ver = _prompt("caption_review_edu")
        rout = os.path.join(workdir, "review.json")
        rprompt = rtpl.format(style=style, caption=caption,
                              alt_texts="\n".join(f"  {i+1}. {a}" for i, a in enumerate(alts)),
                              out_path=rout, **common)
        rok, review = invoke_claude_json(rprompt, workdir, rout, schema=REVIEW_SCHEMA,
                                         stage="caption_review", timeout=C.CAPTION_TIMEOUT)
        verdict = str((review or {}).get("verdict", "UNREVIEWED")).upper() if rok else "UNREVIEWED"
        issues = "; ".join(str(x) for x in ((review or {}).get("issues") or [])) if rok else "review call failed"
        if verdict == "FAIL":
            return _fail(st, number, f"brand/claims review FAILED: {issues}")
        if verdict == "REVISE":
            new = str(review.get("revisedCaption", "")).strip()
            if new and validate_caption(new, style)[0] and new.count(C.SITE_URL) == 1:
                caption = new; log("  review revised the caption")
            new_alts = review.get("revisedAltTexts") or []
            if len(new_alts) == len(ids):
                alts = [str(a) for a in new_alts]

        general = [str(x) for x in (res.get("generalClaims") or [])]
        remark = " | ".join(x for x in [
            str(res.get("remark", "")).strip(),
            f"REVIEW {verdict}: {issues}" if issues else f"REVIEW {verdict}",
            ("GENERAL CLAIMS (verify): " + " / ".join(general)) if general else "",
        ] if x)

        # --- write results: A # · B caption · C..I alt 1-7 · J written date · K remark ---
        now = datetime.datetime.now()
        row = [str(number), caption] + (alts + [""] * MAX_ALTS)[:MAX_ALTS] + [now.strftime("%Y-%m-%d %H:%M"), remark]
        cap_ws.append_row(row, value_input_option="RAW")
        S.set_status(st["row"], "H", "Done")
        S.set_status(st["row"], "I", now.strftime("%Y-%m-%d"))
        S.set_status(st["row"], "J", now.strftime("%H:%M"))
        S.add_remark(st["row"], "CAPTION", f"{style} via {res.get('route', '?')} · {verdict}"
                     + (f" · general claims: {len(general)}" if general else ""))

        # --- learning loop (same repo, same shape as the image lane) ---
        tagline = caption.split("\n")[0]; hashtags = caption.split("\n")[-1]
        push_playbook_entry(mem_dir, (
            f"### {now.strftime('%Y-%m-%d')} · EDUCATIONAL · {series} · {ttype} · queue #{number} · [post URL once live]\n"
            f"- Source: caption_edu v1.0 (auto-chain)\n"
            f"- Style: {style} (route: {res.get('route', '?')})\n"
            f"- Tagline: {tagline}\n"
            f"- Hashtags: {hashtags} [experiment slot: {res.get('experimentTag', '?')}]\n"
            f"- Hashtag rationale: {res.get('hashtagRationale', '—')}\n"
            f"- Hook type: {res.get('hookType', '?')}\n"
            f"- Review: {verdict} {issues}\n"
            f"- Prompt version: caption_edu {cap_ver} · review {rev_ver}\n"))
        append_caption_log(number, "Educational", f"{series} · {ttype}", style,
                           str(res.get("route", "?")), hashtags)
        return True, f"#{number} captioned ({style})"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _fail(st, number, msg):
    log(f"  caption #{number} ERROR: {msg}")
    S.set_status(st["row"], "H", "ERROR")
    S.add_remark(st["row"], "CAPTION", f"ERROR: {msg}")
    return False, msg


def run_pending():
    """Every row with E=Done and H not Done/ERROR/Processing."""
    n = 0
    for st in S.status_rows():
        if (st["words"] == "Approved" and st["render"] == "Done"
                and st["caption"] in ("", "Not Available", "Not Started", "Ready")):
            ok, msg = caption_row(st["num"])
            log(f"caption: {msg}")
            n += 1 if ok else 0
    return f"{n} caption(s) written"


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--number", help="queue # to caption")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.number:
        print(caption_row(a.number, force=a.force))
    else:
        print(run_pending())
