# =============================================================================
# Selene Dreams — Prompt Runner v1.6 (2026-09-16)
# prompt_runner.py — Turn a winning weekly pick into Generation Queue rows
# =============================================================================
#
# Fired by server.py's POST /select when a teammate submits the week's picks
# on the Selene Picks web page. For each picked post:
#
#   1. Download the chosen reference slides (IG CDN URLs — fresh that week).
#   2. Invoke the Claude Code CLI headlessly to LOOK at each slide and write
#      one Selene-style generation prompt per slide (max 3), following the
#      locked prompt-writing rules.
#   3. Append a Generation Queue row (Year/Month/Fabric/Type/Variant +
#      prompts) via the Sheets API, and initialize the row's Generation
#      Status entries (G="Not Available", J="Not Started").
#   4. Log the selection (picks AND passes) to selections.md in the
#      selene-ig-memory repo — the taste model's training signal.
#
# The user then reviews the rows and flips D=Ready as usual. Errors for a
# pick are appended to the Generation Status M column is not possible (no
# row exists yet on error) — they are reported in the Weekly Picks tab's
# Prompt status cell instead, plus the server log.
#
# CLI usage (rerun a pending pick saved in the Weekly Picks tab):
#   python3 rerun_pending_pick.py           <- USE THIS
#
#   --json below takes a file holding the FULL payload {week, picker, picks}.
#   It is NOT the Weekly Picks "Details" cell: picker.gs writes only
#   JSON.stringify(payload.picks) there — the picks array, without the week
#   or picker that run_selection() needs. Pointing --json at that cell hands
#   a bare list to code that calls .get() on it. rerun_pending_pick.py reads
#   the week and picker from columns 1 and 2 and rebuilds the envelope.
#     python3 prompt_runner.py --json '/path/to/full-payload.json'
#
# CHANGELOG
#   1.4  2026-08-31  ARCHIVE FALLBACK for dead CDN slides. A topped-up pick
#                    carries Instagram URLs recorded weeks earlier, so the
#                    entries top-up exists to rescue were precisely the ones
#                    whose downloads 403'd — week 2026-08-31 lost posts #5 and
#                    #7 this way while their images sat in the memory repo the
#                    whole time. download_slides() now falls back to the
#                    archived copy (by origN + archiveWeek) and says so.
#   1.3  2026-08-31  Depend on Sheets alone. get_google_services() eagerly
#                    builds the OAuth Drive client; its token had expired, so
#                    a picks rerun died on a credential this file never used.
#   1.2  2026-08-31  Corrected the recovery instructions above, which
#                    described a --json path that could never have worked,
#                    and added rerun_pending_pick.py as the real one.
#   1.6  2026-09-16  {taste_brief}: the distilled taste brief (taste_brief.py)
#                    goes into every image prompt. Fail-open placeholder.
#   1.5  2026-09-16  References come from DRIVE. reference_section() now
#                    delegates to reference_drive (02. Reference Images /
#                    01. Style, synced into reference-images/style/), and
#                    the run refreshes the cache first, fail-open. The local
#                    folder is a cache; the team drops images in Drive.
#   1.1  2026-08-26  Marcus's reference-images folder feeds prompt writing.
# =============================================================================

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime

import chain          # v14 auto-chain — see chain.py for why this is not a sheet write
import config
import memory_digests
import pipeline_state
from google_services import get_sheets_client
from caption_runner import (
    clone_memory,
    invoke_claude_json,
    load_prompt,
    log,
    week_context,
)

PROMPTS_SCHEMA = {
    "prompts": {"type": "list", "min_len": 1},
    "aestheticNote": {"type": "str", "required": False},
}

PICKS_SHEET = "Weekly Picks"


REFERENCE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
MAX_REFERENCE_IMAGES = 6


def _taste_brief():
    try:
        import taste_brief
        return taste_brief.brief_block("image-prompts")
    except Exception:
        return "(taste brief unavailable this run)"


def reference_section():
    """Marcus's and the team's style references, as a prompt block.

    As of 1.5 these come from Drive "02. Reference Images / 01. Style" via
    reference_drive; the flat local folder is the pre-1.5 fallback. Empty
    string if there is nothing — the template placeholder then disappears."""
    try:
        import reference_drive
        block = reference_drive.section(
            "style", limit=MAX_REFERENCE_IMAGES,
            heading="MARCUS'S OWN STYLE REFERENCES")
        if block:
            return block
    except Exception as e:
        log(f"  reference_drive unavailable ({type(e).__name__}) — "
            f"falling back to the flat local folder")
    d = getattr(config, "REFERENCE_IMAGES_DIR", "")
    try:
        files = [os.path.join(d, f) for f in os.listdir(d)
                 if f.lower().endswith(REFERENCE_EXTS)]
    except OSError:
        return ""
    if not files:
        return ""
    files.sort(key=os.path.getmtime, reverse=True)
    total = len(files)
    files = files[:MAX_REFERENCE_IMAGES]
    lines = "\n".join(f"  - {f}" for f in files)
    suffix = f" (newest {len(files)} of {total})" if total > len(files) else ""
    return (
        f"MARCUS'S OWN STYLE REFERENCES{suffix} — view EVERY file below with "
        f"the Read tool before writing prompts. These are hand-picked examples "
        f"of the kind of content Marcus wants: use them for mood, composition, "
        f"light and styling direction. Precedence: brand-guide.md rules still "
        f"win; these outrank the scraped reference slides on taste. Never copy "
        f"one literally — borrow the feel.\n{lines}\n")


def brand_section_for(mem_dir):
    """What governs the LOOK of the generated images.

    Until 2026-08-12 the prompt runner was the only stage that never read
    brand-guide.md — every other agent treated it as authoritative. That is
    the structural reason generated images stayed indoor-japandi while the
    screener judged references against the deck's world. Fixing it here fixes
    it everywhere, because this is where the aesthetic is actually decided.
    """
    if mem_dir and getattr(config, "BRAND_GUIDE_GOVERNS_PROMPTS", False):
        return (
            f"READ {mem_dir}/brand-guide.md FIRST and treat it as AUTHORITATIVE "
            f"for setting, light, palette, styling and whether people may "
            f"appear. Its photography rules and 12-point rubric decide what "
            f"these images should look like — and they are the same rubric "
            f"your output will be scored against after generation. Where the "
            f"reference photo and the brand guide disagree, the brand guide "
            f"wins.")
    if mem_dir:
        return (
            f"Brand guide available at {mem_dir}/brand-guide.md for tone, but "
            f"the legacy house style governs this run: calm indoor japandi / "
            f"scandinavian / soft-boho interiors, no people in frame, no "
            f"clutter, no competing bedding.")
    return ("No brand files this run — default to calm, elevated, natural "
            "interiors, no people in frame, no clutter.")


def _repo_bytes(path):
    """Fetch a file from the memory repo.

    Slides carried over from an earlier week live in the repo, not on
    Instagram's CDN — their original links expired within days of being
    scraped. The picker sends those as "repo:<path>" markers.
    """
    with open(os.path.join(config.BASE_DIR, "github_token.txt")) as f:
        token = f.read().strip()
    url = ("https://api.github.com/repos/leemarcusmz/selene-ig-memory/"
           f"contents/{path}")
    req = urllib.request.Request(url, headers={
        "Authorization": "token " + token,
        "Accept": "application/vnd.github.raw+json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def archive_fallback(mem, week, post_url, url):
    """Local archived bytes for a slide whose CDN link has died, or None.

    A TOPPED-UP pick carries the live Instagram URLs recorded weeks ago, when
    its post was first scraped, and those 403 within days — so exactly the
    entries top-up exists to rescue are the ones whose downloads fail. Their
    images were archived at screening time under their OWN week, which is what
    picker.gs uses to render them. This is the same lookup, for the same
    reason, on the prompt-writing side.

    Resolution is by postUrl -> the shortlist entry, then origN + archiveWeek
    (the archive is keyed by the ORIGINAL candidate number, never the display
    number) and the slide's position in that entry's images list. Read from
    the already-cloned repo, so no network and no token.
    """
    try:
        with open(os.path.join(mem, "shortlists", f"shortlist-{week}.json")) as f:
            entries = json.load(f).get("entries", [])
    except Exception:
        return None
    for e in entries:
        if e.get("postUrl") != post_url:
            continue
        imgs = e.get("images") or []
        if url not in imgs:
            return None
        i = imgs.index(url) + 1
        n = e.get("origN", e.get("n"))
        name = f"cand_{n}.jpg" if i == 1 else f"cand_{n}_s{i}.jpg"
        path = os.path.join(mem, "candidate-images",
                            e.get("archiveWeek") or week, name)
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
        return None
    return None


def download_slides(urls, img_dir, fallback=None):
    os.makedirs(img_dir, exist_ok=True)
    saved = 0
    for i, u in enumerate(urls, 1):
        data = None
        try:
            if str(u).startswith("repo:"):
                data = _repo_bytes(str(u)[5:])
            else:
                req = urllib.request.Request(
                    u, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = r.read()
        except Exception as e:
            if fallback:
                data = fallback(u)
            if data:
                # The archive is a 640px q65 thumbnail, not the CDN original.
                # Ample for LOOKING at a reference to write a prompt from; say
                # so plainly rather than letting a quality drop pass silently.
                log(f"    slide {i}: CDN dead ({e}) — using archived copy "
                    f"(640px thumbnail)")
            else:
                log(f"    slide {i} download failed: {e}")
                continue
        try:
            with open(os.path.join(img_dir, f"slide_{i:02d}.jpg"), "wb") as f:
                f.write(data)
            saved += 1
        except Exception as e:
            log(f"    slide {i} could not be written: {e}")
    return saved


def first_empty_queue_row(queue):
    """Occupied if any of Year, Fabric, Prompt 1 has content (append_row rule)."""
    year_vals = queue.col_values(config.COL_YEAR + 1)
    fabric_vals = queue.col_values(config.COL_FABRIC + 1)
    p1_vals = queue.col_values(config.COL_PROMPT_1 + 1)

    def cell(vals, i):
        return vals[i - 1] if i <= len(vals) else ""

    last = max(len(year_vals), len(fabric_vals), len(p1_vals))
    for i in range(2, last + 1):
        if not any(str(cell(v, i)).strip()
                   for v in (year_vals, fabric_vals, p1_vals)):
            return i
    return last + 1


# A Generation Queue row has exactly five Prompt columns and one picked post
# becomes one row, so this is a schema limit rather than a policy one. The
# credit ceiling now lives in picker.gs (WEEKLY_IMAGE_CAP) — raised from 3 on
# 2026-08-17 because capping each row separately threw away usable slides.
MAX_PROMPTS_PER_ROW = 5


def append_queue_row(queue, product, prompts):
    row = first_empty_queue_row(queue)
    now = datetime.now()
    queue.update_cell(row, config.COL_YEAR + 1, str(now.year))
    queue.update_cell(row, config.COL_MONTH + 1, now.strftime("%B"))
    queue.update_cell(row, config.COL_FABRIC + 1, product.get("fabric", ""))
    queue.update_cell(row, config.COL_PRODUCT_TYPE + 1, product.get("productType", ""))
    queue.update_cell(row, config.COL_VARIANT + 1, product.get("variant", ""))
    for i, col in enumerate(config.PROMPT_COLS[:3]):
        queue.update_cell(row, col + 1, prompts[i] if i < len(prompts) else "")
    return row


def init_generation_status(queue, number):
    """Seed the control-panel row, then START GENERATION.

    v14 (2026-08-21): D is now set to Ready here instead of waiting for a
    human flip. That flip is what stranded rows 17-21 — their prompts were
    written on 2026-08-13 and nobody ever set the status, so generation never
    began and they sat for over a week.

    Setting D and firing are two separate acts on purpose: the cell is the
    record, the local call is the transport. Writing "Ready" through the
    Sheets API does NOT fire trigger.gs (on-edit triggers ignore API writes),
    so the fire has to be explicit. See chain.py.
    """
    try:
        gs = queue.spreadsheet.worksheet(config.GS_SHEET_NAME)
        gs_row = number + config.GS_FIRST_DATA_ROW - 1
        gs.update_cell(gs_row, config.GS_COL_CAP_STATUS,
                       config.CAP_STATUS_NOT_AVAILABLE)
        gs.update_cell(gs_row, config.GS_COL_POST_STATUS, "Not Started")
        gs.update_cell(gs_row, config.GS_COL_GEN_STATUS, config.STATUS_READY)
    except Exception as e:
        log(f"    NOTE: Generation Status init failed for #{number}: {e}")
        return
    if chain.fire_generation(number, queue_sheet=queue):
        log(f"    → generating #{number} now (auto-chain)")
    else:
        log(f"    → #{number} is Ready but generation did not start; "
            f"see System Remark(s) on the row")


def update_pick_status(spreadsheet, week, status):
    try:
        sh = spreadsheet.worksheet(PICKS_SHEET)
        for i, w in enumerate(sh.col_values(1), start=1):
            if i >= 2 and str(w).strip() == str(week).strip():
                sh.update_cell(i, 6, status)
                return
    except Exception as e:
        log(f"    NOTE: could not update Weekly Picks status: {e}")


PLAYBOOK_FILE = "prompt-playbook.md"

PLAYBOOK_HEADER = """# Selene Prompt Playbook

Every generation prompt this pipeline has written, and what it produced.

Written in two passes: `prompt_runner.py` logs the prompts when a weekly pick
becomes queue rows, then `qa_runner.py` fills in the QA line once the images
have been generated and scored against brand-guide.md's 12-point rubric.

This is the only place where prompt wording can be tied to output quality.
Read it before writing new prompts: prefer the phrasings that scored well,
and avoid the shapes that repeatedly produced low scores or fidelity misses.
"""


def append_prompt_entry(mem_dir, number, week, picker, product, prompts, pick,
                        version=None, aesthetic_note=None):
    """Log the prompts for queue row #number. QA line is filled in later by
    qa_runner.py. Non-fatal — prompts are already in the sheet."""
    if not mem_dir:
        return
    try:
        path = os.path.join(mem_dir, PLAYBOOK_FILE)
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write(PLAYBOOK_HEADER)
        lines = [
            f"\n### ROW {number} · {datetime.now().strftime('%Y-%m-%d')} · "
            f"{product.get('fabric','?')} {product.get('productType','?')} "
            f"{product.get('variant','?')}",
            f"- Week {week} · picked by {picker} · "
            f"reference: {pick.get('postUrl','?')}",
            f"- Concept: {pick.get('concept','—')}",
            f"- Prompts written: {len(prompts)}",
        ]
        for i, p in enumerate(prompts, 1):
            lines.append(f"  {i}. {p}")
        if version:
            lines.append(f"- Prompt-writer version: {version}"
                         + (f" · aesthetic: {aesthetic_note}"
                            if aesthetic_note else ""))
        lines.append("- QA: pending")
        with open(path, "a") as f:
            f.write("\n".join(lines) + "\n")
        log(f"    → prompt-playbook entry for row #{number}")
    except Exception as e:
        log(f"    NOTE: prompt-playbook entry failed for #{number}: {e}")


def log_selection(mem_dir, week, picker, picks):
    if not mem_dir:
        return
    try:
        picked = ", ".join(
            f"#{p['n']} {p.get('postUrl','')}" for p in picks)
        entry = (f"\n### {datetime.now().strftime('%Y-%m-%d')} · "
                 f"Weekly pick (web picker) · week {week}\n"
                 f"- PICKED by {picker}: {picked}\n"
                 f"- PASSED: all other shortlist numbers that week\n")
        with open(os.path.join(mem_dir, "selections.md"), "a") as f:
            f.write(entry)
        pipeline_state.mirror_to_memory(mem_dir)
        ok, msg = pipeline_state.push_with_retry(
            mem_dir, f"Log selection week {week}", logger=log)
        if not ok:
            log(f"    NOTE: selections.md push failed: {msg}")
    except Exception as e:
        log(f"    NOTE: selections.md push failed: {e}")


def run_selection(payload):
    """payload: {week, picker, picks:[{n, postUrl, concept, product, slideUrls}]}"""
    week = payload.get("week", "?")
    with pipeline_state.stage(pipeline_state.PICKS, week=week,
                              picker=payload.get("picker", "?")) as st:
        return pipeline_state.finish(_run_selection(payload), st)


def _run_selection(payload):
    week = payload.get("week", "?")
    picker = payload.get("picker", "?")
    picks = payload.get("picks", [])
    log(f"Selection run — week {week}, picked by {picker}, {len(picks)} post(s).")

    # Refresh the reference cache from Drive first. Fail-open: a dead Drive
    # token (the known failure) means the prompts use whatever was cached.
    try:
        import reference_drive
        n_new, n_gone = reference_drive.refresh()
        if n_new or n_gone:
            log(f"  references: {n_new} new, {n_gone} withdrawn")
    except Exception as e:
        log(f"  reference refresh skipped ({type(e).__name__})")

    # Sheets ONLY. get_google_services() also builds the OAuth Drive client,
    # whose token expires and needs an interactive browser re-auth — and this
    # function never touched Drive, it discarded it. On 2026-08-31 that dead
    # token blocked a weekly pick rerun for a service the code does not use.
    sheets_client = get_sheets_client()
    spreadsheet = sheets_client.open_by_key(config.GOOGLE_SHEET_ID)
    queue = spreadsheet.worksheet(config.GOOGLE_SHEET_NAME)

    workdir = tempfile.mkdtemp(prefix="selene_picks_")
    added, failed = [], []
    try:
        mem_dir = clone_memory(workdir)
        brand_section = brand_section_for(mem_dir)
        context = week_context(mem_dir)
        # The reading half of the loop: what past prompts actually produced.
        playbook = memory_digests.playbook_digest(mem_dir)
        for p in picks:
            n = p.get("n")
            product = p.get("product") or {}
            urls = (p.get("slideUrls") or [])[:MAX_PROMPTS_PER_ROW]
            log(f"  Post #{n}: {product.get('fabric')}/"
                f"{product.get('productType')}/{product.get('variant')} — "
                f"{len(urls)} slide(s)")
            img_dir = os.path.join(workdir, f"post_{n}")
            got = download_slides(
                urls, img_dir,
                fallback=lambda u, _m=mem_dir, _w=week, _p=p.get("postUrl"):
                    archive_fallback(_m, _w, _p, u))
            if got == 0:
                failed.append(f"#{n}: no slides downloadable (CDN expired?)")
                continue

            out_path = os.path.join(workdir, f"result_{n}.json")
            template, version = load_prompt("image-prompts")
            prompt = template.format(
                fabric=product.get("fabric", ""),
                product_type=product.get("productType", ""),
                variant=product.get("variant", ""),
                img_dir=img_dir, n_images=got,
                concept=p.get("concept", "(none)"),
                brand_section=brand_section, week_context=context,
                reference_section=reference_section(),
                taste_brief=_taste_brief(),
                playbook_section=playbook, out_path=out_path,
            )
            ok, result = invoke_claude_json(
                prompt, workdir, out_path, schema=PROMPTS_SCHEMA,
                stage="prompts")
            if not ok:
                failed.append(f"#{n}: {result}")
                continue
            prompts = [str(x).strip() for x in result.get("prompts", [])
                       if str(x).strip()]
            if not prompts:
                failed.append(f"#{n}: empty prompts")
                continue

            row = append_queue_row(queue, product, prompts[:MAX_PROMPTS_PER_ROW])
            init_generation_status(queue, row - 1)
            added.append(row - 1)
            log(f"    → queue row #{row - 1} ({len(prompts[:MAX_PROMPTS_PER_ROW])} prompts)")
            append_prompt_entry(mem_dir, row - 1, week, picker, product,
                                prompts[:MAX_PROMPTS_PER_ROW], p, version=version,
                                aesthetic_note=result.get("aestheticNote"))
            pipeline_state.record(
                pipeline_state.PROMPTS, "ok", row=row - 1, week=week,
                message=f"{len(prompts[:MAX_PROMPTS_PER_ROW])} prompt(s) written",
                product=f"{product.get('fabric','')} "
                        f"{product.get('productType','')} "
                        f"{product.get('variant','')}".strip(),
                referenceUrl=p.get("postUrl", ""))

        status = (f"Rows #{', #'.join(map(str, added))} added"
                  if added else "FAILED — no rows added")
        if failed:
            status += f" · issues: {'; '.join(failed)}"
        update_pick_status(spreadsheet, week, status)
        log_selection(mem_dir, week, picker, picks)
        log(f"Done: {len(added)} row(s) added, {len(failed)} issue(s).")
        return (len(added) > 0), status
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="Selene prompt runner")
    parser.add_argument("--json", required=True,
                        help="Path to a /select payload JSON file")
    args = parser.parse_args()
    with open(args.json) as f:
        payload = json.load(f)
    ok, msg = run_selection(payload)
    print(("SUCCESS: " if ok else "FAILED: ") + msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
