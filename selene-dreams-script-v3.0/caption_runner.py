# =============================================================================
# Selene Dreams — Caption Runner v1.2 (2026-09-16)
# caption_runner.py — Caption generation, fired by the v14 auto-chain
#
# CHANGELOG
#   v1.2  2026-09-16 — {taste_brief}: the distilled taste brief goes into every
#                      caption prompt (caption.md v5). Fail-open.
#   v1.1  2026-09-07 — Seven caption STYLES replace the locked 5-line shape.
#         The old len(caption.split()) != 5 gate is gone; validate_caption()
#         checks each style against its own shape plus the shared hashtag and
#         dash rules. Same fix applied to the REVISE path, which silently
#         discarded any revised caption that was not 5 lines. Adds the style
#         rotation log (caption-log.md) that the recency filter reads and the
#         runner now writes. Prompt gains format/notes/recent-styles context.
#   v1.0  2026-07-22 — first version, locked 5-line format.
# =============================================================================
#
# EVENT DRIVEN, NOT POLLED. Since the v14 auto-chain (2026-08-21) generate.py
# calls chain.fire_caption() the moment images finish, which POSTs /caption to
# the local server; server.py calls run_caption() in a background thread. No
# hourly trigger, no human flipping G. Everything happens locally on the Mac:
#
#   1. Read the row's product info + generated images from the Generation
#      Queue (via Sheets/Drive APIs — full-size images, no 10 MB limit).
#   2. Invoke the Claude Code CLI headlessly (`claude -p`) to LOOK at every
#      image and write the locked-format caption + per-image alt text,
#      informed by the selene-ig-memory learning files.
#   3. Write the caption row into the "Generated Caption" tab and update the
#      Generation Status row (G=Done, H/I completion date/time) via the
#      Sheets API — no browser involved.
#   4. Log the caption to copy-playbook.md and push to selene-ig-memory.
#
# On any failure: G=ERROR and an appended "CAPTION: ..." entry in System
# Remark(s) col M.
#
# CLI usage:
#   python3 caption_runner.py --number 14      # caption queue row #14
#   python3 caption_runner.py --all-ready      # caption every G=Ready row
#
# Requirements: the Claude Code CLI installed and logged in (`claude` on
# PATH), plus the same credentials.json / token.json as the generation flow.
# =============================================================================

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

import config
import pipeline_state
# Re-exported so the other runners can keep importing these from here.
from claude_client import (  # noqa: F401
    log,
    invoke_claude,
    invoke_claude_json,
    load_prompt,
    week_context,
)
from google_services import (
    get_google_services,
    download_file_from_drive,
    get_gs_sheet,
    find_gs_row,
    gs_write,
    gs_append_remark,
)

MEMORY_REPO = "https://x-access-token:{token}@github.com/leemarcusmz/selene-ig-memory.git"
MEMORY_TOKEN_FILE = os.path.join(config.BASE_DIR, "github_token.txt")

CAPTION_SHEET_NAME = "Generated Caption"

# --- Caption styles (v1.1) -------------------------------------------------
# The register the prompt routes across. Order is not priority.
VALID_STYLES = [
    "One Line", "Two Beat", "Meet the Product", "Three Beats",
    "The Detail", "Care Note", "Current Style",
]
BANNED_TAGS = {
    "#fyp", "#explorepage", "#viral", "#explore",
    "#followforfollow", "#likeforlike", "#instagood",
}
# Rotation history the recency filter reads. Absolute on purpose: this runner
# is always on the Mac, and "~" resolves elsewhere under other shells. Override
# with SELENE_CAPTION_LOG for testing. Could move to config.py if another
# runner ever needs it.
CAPTION_LOG_PATH = os.environ.get(
    "SELENE_CAPTION_LOG",
    "/Users/marcuslee/Desktop/Selene Dreams/03. Content/"
    "00. Social Media Posts/caption-log.md",
)
CAPTION_HEADER_ROW = 1  # data from row 2; cols: A # | B Caption | C-G Alt 1-5 | H Remark


# --- Output schemas (validated by claude_client, with one repair attempt) ---
CAPTION_SCHEMA = {
    "caption": {"type": "str", "min_len": 10},
    "style": {"type": "str"},
    "route": {"type": "str", "required": False},
    "altTexts": {"type": "list", "min_len": 1},
    "remark": {"type": "str", "required": False},
    "hookType": {"type": "str", "required": False},
    "experimentTag": {"type": "str", "required": False},
    "hashtagRationale": {"type": "str", "required": False},
}

REVIEW_SCHEMA = {
    "verdict": {"type": "str", "choices": ["PASS", "REVISE", "FAIL"]},
    "issues": {"type": "list", "required": False},
    "revisedCaption": {"type": "str", "required": False},
    "revisedAltTexts": {"type": "list", "required": False},
    "notes": {"type": "str", "required": False},
}


# =============================================================================
# MEMORY REPO
# =============================================================================

def _read_memory_token():
    if os.path.exists(MEMORY_TOKEN_FILE):
        with open(MEMORY_TOKEN_FILE) as f:
            return f.read().strip()
    return None


def _taste_brief_block():
    try:
        import taste_brief
        return taste_brief.brief_block("caption")
    except Exception:
        return "(taste brief unavailable this run)"


def clone_memory(workdir):
    """Clone selene-ig-memory for the learning files. Non-fatal on failure."""
    token = _read_memory_token()
    if not token:
        log("  NOTE: github_token.txt not found — running without learning files.")
        return None
    dest = os.path.join(workdir, "mem")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", MEMORY_REPO.format(token=token), dest],
            check=True, capture_output=True, timeout=120,
        )
        return dest
    except Exception as e:
        log(f"  NOTE: memory clone failed ({e}) — proceeding without it.")
        return None


def push_playbook_entry(mem_dir, entry):
    """Append the caption log entry to copy-playbook.md and push. Non-fatal."""
    if not mem_dir:
        return
    try:
        with open(os.path.join(mem_dir, "copy-playbook.md"), "a") as f:
            f.write("\n" + entry.rstrip() + "\n")
        pipeline_state.mirror_to_memory(mem_dir)
        ok, msg = pipeline_state.push_with_retry(
            mem_dir, f"Caption runner {datetime.now().strftime('%Y-%m-%d')}",
            logger=log)
        log(f"  Playbook entry: {msg}" if ok
            else f"  NOTE: playbook push failed ({msg}) — captions are still "
                 f"in the sheet.")
    except Exception as e:
        log(f"  NOTE: playbook push failed ({e}) — captions are still in the sheet.")


# =============================================================================
# STYLE VALIDATION + ROTATION LOG (v1.1)
# =============================================================================
# Replaces the old "exactly 5 lines" gate. Each style is checked against its
# own shape; the hashtag and dash rules are shared by all seven.

def validate_caption(caption, style):
    """Return (ok, message). Never raises."""
    if style not in VALID_STYLES:
        return False, f"unknown style {style!r}"
    if "\u2014" in caption or "\u2013" in caption:
        return False, "caption contains an em or en dash"

    lines = caption.split("\n")
    blocks = [l.strip() for l in lines if l.strip()]
    if not blocks:
        return False, "empty caption"

    tags = blocks[-1].split()
    if not tags or not all(t.startswith("#") for t in tags):
        return False, "last line is not the hashtag line"
    if not 3 <= len(tags) <= 5:
        return False, f"{len(tags)} hashtags, expected 3 to 5"
    low = [t.lower() for t in tags]
    if any(t != l for t, l in zip(tags, low)):
        return False, "hashtags must be lowercase"
    if low.count("#selenedreams") != 1:
        return False, "#selenedreams must appear exactly once"
    if low[-1] != "#selenedreams":
        return False, "#selenedreams must be the last tag"
    hit = BANNED_TAGS & set(low)
    if hit:
        return False, f"reach-farming tag(s): {', '.join(sorted(hit))}"

    if style == "Current Style":
        if len(lines) != 5:
            return False, f"Current Style must be exactly 5 lines, got {len(lines)}"
        if lines[1].strip() != "." or lines[3].strip() != ".":
            return False, "Current Style needs a literal period on lines 2 and 4"
        return True, "ok"

    if any(l.strip() == "." for l in lines):
        return False, f"{style} must not use period separator lines"
    body = blocks[:-1]
    if not body:
        return False, f"{style} has no caption body"
    if len(body) > 3:
        return False, f"{style} has {len(body)} paragraphs, max 3"
    if style in ("One Line", "Two Beat", "Three Beats") and len(body) != 1:
        return False, f"{style} must be a single paragraph, got {len(body)}"
    if style == "Three Beats":
        frags = [f for f in re.split(r"(?<=[.!?])\s+", body[0]) if f.strip()]
        if len(frags) != 3:
            return False, f"Three Beats needs exactly 3 fragments, found {len(frags)}"
    if style == "One Line":
        words = len(body[0].split())
        if words > 14:
            return False, f"One Line is {words} words, max 14"
    return True, "ok"


def read_recent_styles(limit=12):
    """Most recent first. Empty list if the log is missing or unreadable."""
    try:
        with open(CAPTION_LOG_PATH) as f:
            rows = [l for l in f if l.lstrip().startswith("|")]
    except Exception as e:
        log(f"  NOTE: caption log unreadable ({e}) — recency filter is blind "
            f"this run.")
        return []
    out = []
    for line in rows:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        if cells[3] in VALID_STYLES:
            out.append(cells[3])
    return out[::-1][:limit]


def format_recent_styles(styles):
    if not styles:
        return ("(no history yet — the log is empty or unreadable, so no style "
                "is blocked this run)")
    return "\n".join(f"{i}. {s}" for i, s in enumerate(styles, 1))


def append_caption_log(number, lane, product, style, route, tags):
    """Append one rotation row. Non-fatal, but logged loudly: if this stops
    happening the recency filter goes blind and the rotation collapses."""
    row = (f"| {datetime.now().strftime('%Y-%m-%d')} | {lane} | {product} | "
           f"{style} | {route} | {tags} |  |  |\n")
    try:
        with open(CAPTION_LOG_PATH, "a") as f:
            f.write(row)
        log(f"  Rotation log: recorded {style}.")
    except Exception as e:
        log(f"  WARNING: could not write caption-log.md ({e}). The style "
            f"rotation is now blind for the next run — fix this before the "
            f"next post.")


# =============================================================================
# CLAUDE CLI
# =============================================================================

def build_memory_section(mem_dir):
    if not mem_dir:
        return ("No learning files available this run — use best judgment for "
                "keywords and hashtags, calm Selene voice.")
    return (
        f"LEARNING FILES (read these first):\n"
        f"- {mem_dir}/keyword-bank.md — use ACTIVE transactional terms front-loaded; "
        f"TESTING sparingly; never RETIRED; never claim specs the site doesn't.\n"
        f"- {mem_dir}/hooks-library.md — Proven hook patterns, filtered through "
        f"Selene's calm voice.\n"
        f"- {mem_dir}/copy-playbook.md — avoid repeating recent taglines, hashtag "
        f"combos, and experiment-slot tags."
    )


# =============================================================================
# BRAND REVIEW GATE (added 2026-08-12)
# =============================================================================
# A caption is never written to the sheet on the strength of one draft. A
# second, independent pass reviews it against brand-guide.md the way a brand
# manager would — voice, substantiation, hashtag discipline, alt-text quality
# — and may rewrite it once. Modelled on the marketing:brand-review skill:
# findings are severity-graded, and only a genuine factual/compliance problem
# blocks the write.

def review_caption(workdir, mem_dir, caption, alt_texts, fabric,
                   product_type, variant, img_dir, style):
    """Second-pass brand review. Returns the review dict, or None if the
    reviewer could not run (non-fatal — the draft then goes through
    unreviewed and is marked as such)."""
    out_path = os.path.join(workdir, "review.json")
    brand_section = (
        f"AUTHORITATIVE BRAND REFERENCE: read {mem_dir}/brand-guide.md FIRST — "
        f"its voice and photography rules govern this review. Also check "
        f"{mem_dir}/copy-playbook.md so this caption is not a near-repeat of a "
        f"recent one (same tagline shape, same hashtag set)."
        if mem_dir else
        "No brand files available this run — review against general Selene "
        "voice: calm, elevated, sensory, never hypey. Be conservative."
    )
    alt_block = "\n".join(f"{i}. {a}" for i, a in enumerate(alt_texts, 1))
    template, version = load_prompt("caption-review")
    prompt = template.format(
        brand_section=brand_section, fabric=fabric, product_type=product_type,
        variant=variant, img_dir=img_dir, n_images=len(alt_texts),
        caption=caption, alt_block=alt_block, out_path=out_path,
        style=style,
    )
    log(f"  Brand review pass (prompt {version})...")
    ok, result = invoke_claude_json(
        prompt, workdir, out_path, schema=REVIEW_SCHEMA,
        stage="caption_review", timeout=600)
    if not ok:
        log(f"  NOTE: brand review could not run ({result}) — caption goes "
            f"through unreviewed.")
        return None
    result["_promptVersion"] = version
    return result


def summarize_review(review):
    """Compact one-line verdict for the sheet remark + playbook."""
    if not review:
        return "UNREVIEWED (reviewer unavailable)"
    verdict = str(review.get("verdict", "?")).upper()
    issues = review.get("issues") or []
    if not issues:
        return verdict
    parts = [f"{i.get('check','?')}: {i.get('detail','')}".strip()
             for i in issues if isinstance(i, dict)]
    return f"{verdict} — " + " · ".join(parts)


# =============================================================================
# SHEET HELPERS
# =============================================================================

def get_caption_sheet(queue_sheet):
    return queue_sheet.spreadsheet.worksheet(CAPTION_SHEET_NAME)


def caption_row_exists(cap_sheet, number):
    for v in cap_sheet.col_values(1)[CAPTION_HEADER_ROW:]:
        if str(v).strip() == str(number):
            return True
    return False


def append_caption_row(cap_sheet, number, caption, alt_texts, remark):
    col_a = cap_sheet.col_values(1)
    next_row = max(len(col_a), CAPTION_HEADER_ROW) + 1
    alts = (list(alt_texts) + [""] * 5)[:5]
    cap_sheet.update(
        f"A{next_row}:H{next_row}",
        [[number, caption] + alts + [remark or ""]],
        value_input_option="RAW",
    )
    return next_row


def extract_drive_ids(image_urls_cell):
    return re.findall(r"/file/d/([A-Za-z0-9_\-]+)", image_urls_cell or "")


# =============================================================================
# CORE
# =============================================================================

def run_caption(number, sheets_client=None, drive_service=None, force=False):
    with pipeline_state.stage(pipeline_state.CAPTION, row=number) as st:
        return pipeline_state.finish(
            _run_caption(number, sheets_client, drive_service, force), st)


def _run_caption(number, sheets_client=None, drive_service=None, force=False):
    """
    Generate the caption for queue row # `number`. Returns (ok, message).
    Writes all results/statuses to the sheet itself.

    Requires the row's caption Status (col G) to be 'Ready' unless force=True
    — and flips it to 'Processing' while working so the sheet shows progress
    (mirrors the image flow's D=Processing lock).
    """
    log(f"Caption run for #{number}...")
    if sheets_client is None or drive_service is None:
        sheets_client, drive_service = get_google_services()
    spreadsheet = sheets_client.open_by_key(config.GOOGLE_SHEET_ID)
    queue = spreadsheet.worksheet(config.GOOGLE_SHEET_NAME)

    gs = get_gs_sheet(queue)
    gs_row = find_gs_row(gs, number) if gs is not None else None

    def fail(msg):
        log(f"  ERROR: {msg}")
        if gs is not None:
            gs_write(gs, gs_row, config.GS_COL_CAP_STATUS, config.CAP_STATUS_ERROR)
            gs_append_remark(gs, gs_row, f"CAPTION: {msg}")
        return False, msg

    # --- Guards ---
    if gs is not None:
        d_status = str(gs.cell(gs_row, config.GS_COL_GEN_STATUS).value or "").strip()
        if d_status != config.STATUS_DONE:
            gs_write(gs, gs_row, config.GS_COL_CAP_STATUS,
                     config.CAP_STATUS_NOT_AVAILABLE)
            gs_append_remark(
                gs, gs_row,
                f"CAPTION: cannot start — image Status is "
                f"'{d_status or 'blank'}', not Done.")
            return False, "Images not Done"

        g_status = str(gs.cell(gs_row, config.GS_COL_CAP_STATUS).value or "").strip()
        if g_status != config.CAP_STATUS_READY and not force:
            msg = (f"#{number} caption Status is '{g_status or 'blank'}', "
                   f"not 'Ready'. Skipping (use --force to override).")
            log(f"  {msg}")
            return False, msg

        # Lock the row so the sheet shows progress (mirrors D=Processing)
        gs_write(gs, gs_row, config.GS_COL_CAP_STATUS,
                 config.CAP_STATUS_PROCESSING)

    queue_row = number + 1
    row = queue.row_values(queue_row)
    while len(row) < config.TOTAL_COLS:
        row.append("")
    fabric = row[config.COL_FABRIC].strip()
    product_type = row[config.COL_PRODUCT_TYPE].strip()
    variant = row[config.COL_VARIANT].strip()
    notes = row[config.COL_NOTES].strip()
    image_ids = extract_drive_ids(row[config.COL_IMAGE_URLS])
    if not image_ids:
        return fail("no Image URLs on the queue row.")

    cap_sheet = get_caption_sheet(queue)
    if caption_row_exists(cap_sheet, number):
        return fail(f"Generated Caption tab already has a row for #{number} — "
                    f"delete it first if you want a regeneration.")

    workdir = tempfile.mkdtemp(prefix=f"selene_caption_{number}_")
    try:
        # --- Download images ---
        img_dir = os.path.join(workdir, "images")
        os.makedirs(img_dir)
        log(f"  Downloading {len(image_ids)} image(s)...")
        for i, fid in enumerate(image_ids, 1):
            data = download_file_from_drive(drive_service, fid)
            with open(os.path.join(img_dir, f"image_{i:02d}.png"), "wb") as f:
                f.write(data)

        # --- Learning files ---
        mem_dir = clone_memory(workdir)

        # --- Claude ---
        out_path = os.path.join(workdir, "result.json")
        template, cap_version = load_prompt("caption")
        prompt = template.format(
            fabric=fabric, product_type=product_type, variant=variant,
            img_dir=img_dir, n_images=len(image_ids),
            memory_section=build_memory_section(mem_dir),
            week_context=week_context(mem_dir),
            out_path=out_path,
            format_kind=("single image" if len(image_ids) == 1
                         else "carousel (no words on slides)"),
            notes_line=(notes or "(none)"),
            recent_styles=format_recent_styles(read_recent_styles()),
            taste_brief=_taste_brief_block(),
        )
        log(f"  Invoking Claude Code CLI (prompt {cap_version}; this can take "
            f"a few minutes)...")
        ok, result = invoke_claude_json(
            prompt, workdir, out_path, schema=CAPTION_SCHEMA, stage="caption")
        if not ok:
            return fail(result)

        caption = str(result.get("caption", "")).strip()
        alt_texts = result.get("altTexts", [])
        remark = str(result.get("remark", "")).strip()
        style = str(result.get("style", "")).strip()
        route = str(result.get("route", "")).strip() or "?"
        ok_fmt, fmt_msg = validate_caption(caption, style)
        if not caption or not ok_fmt:
            return fail(f"caption rejected ({style or 'no style'}): {fmt_msg}")
        if len(alt_texts) != len(image_ids):
            return fail(f"expected {len(image_ids)} alt texts, got {len(alt_texts)}.")

        # --- Brand review gate ---
        review = review_caption(workdir, mem_dir, caption, alt_texts, fabric,
                                product_type, variant, img_dir, style)
        verdict = str((review or {}).get("verdict", "UNREVIEWED")).upper()
        review_line = summarize_review(review)

        if verdict == "FAIL":
            return fail(f"brand review FAILED — {review_line}")

        if verdict == "REVISE":
            new_caption = str(review.get("revisedCaption", "")).strip()
            ok_rev, rev_msg = (validate_caption(new_caption, style)
                               if new_caption else (False, "empty"))
            if ok_rev:
                caption = new_caption
                log("  Brand review revised the caption.")
            elif new_caption:
                log(f"  NOTE: revised caption failed validation ({rev_msg}) — "
                    f"keeping the draft.")
            else:
                log("  NOTE: review asked for revision but returned no usable "
                    "caption — keeping the draft, flagged in the remark.")
            new_alts = review.get("revisedAltTexts") or []
            if len(new_alts) == len(image_ids):
                alt_texts = [str(a) for a in new_alts]

        remark = " | ".join(x for x in [remark, f"REVIEW: {review_line}"] if x)

        # --- Write results ---
        log(f"  Writing caption row + statuses (review: {verdict})...")
        append_caption_row(cap_sheet, number, caption, alt_texts, remark)
        now = datetime.now()
        if gs is not None:
            gs_write(gs, gs_row, config.GS_COL_CAP_STATUS, config.CAP_STATUS_DONE)
            gs_write(gs, gs_row, config.GS_COL_CAP_DATE, now.strftime("%Y-%m-%d"))
            gs_write(gs, gs_row, config.GS_COL_CAP_TIME, now.strftime("%H:%M"))
            if remark:
                gs_append_remark(gs, gs_row, f"CAPTION note: {remark}")

        # --- Playbook ---
        tagline = caption.split("\n")[0]
        hashtags = caption.split("\n")[-1]
        push_playbook_entry(mem_dir, (
            f"### {now.strftime('%Y-%m-%d')} · {fabric} {product_type} {variant} "
            f"· row #{number} · [post URL once live]\n"
            f"- Source: caption_runner v1.1 (auto-chain)\n"
            f"- Style: {style} (route: {route})\n"
            f"- Tagline: {tagline}\n"
            f"- Hashtags: {hashtags} [experiment slot: "
            f"{result.get('experimentTag', '?')}]\n"
            f"- Hashtag rationale: {result.get('hashtagRationale', '—')}\n"
            f"- Hook type: {result.get('hookType', '?')}\n"
            f"- Brand review: {review_line}\n"
            f"- Prompt version: caption {cap_version}"
            f" · review {(review or {}).get('_promptVersion', 'n/a')}\n"
            + (f"- Flag: {str(result.get('remark', '')).strip()}\n"
               if str(result.get('remark', '')).strip() else "")
        ))

        append_caption_log(number, "Image",
                           f"{fabric} {product_type} {variant}".strip(),
                           style, route, hashtags)
        log(f"  Done — #{number} captioned as {style} "
            f"({len(alt_texts)} alt texts).")
        return True, f"Captioned #{number}"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def run_all_ready():
    sheets_client, drive_service = get_google_services()
    spreadsheet = sheets_client.open_by_key(config.GOOGLE_SHEET_ID)
    queue = spreadsheet.worksheet(config.GOOGLE_SHEET_NAME)
    gs = get_gs_sheet(queue)
    if gs is None:
        log("Generation Status tab unavailable; nothing to do.")
        return 0, 0
    values = gs.get_all_values()
    numbers = []
    for i, r in enumerate(values, start=1):
        if i < config.GS_FIRST_DATA_ROW:
            continue
        num = str(r[config.GS_COL_NUMBER - 1]).strip() \
            if len(r) >= config.GS_COL_NUMBER else ""
        st = str(r[config.GS_COL_CAP_STATUS - 1]).strip() \
            if len(r) >= config.GS_COL_CAP_STATUS else ""
        if num and st == config.CAP_STATUS_READY:
            numbers.append(int(num))
    if not numbers:
        log("No G=Ready rows.")
        return 0, 0
    succ = fail_n = 0
    for n in numbers:
        ok, _ = run_caption(n, sheets_client, drive_service)
        succ += ok
        fail_n += (not ok)
    return succ, fail_n


def main():
    parser = argparse.ArgumentParser(description="Selene caption runner")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--number", type=int, help="Queue # to caption")
    group.add_argument("--all-ready", action="store_true",
                       help="Caption every Generation Status G=Ready row")
    parser.add_argument("--force", action="store_true",
                        help="Run even if caption Status isn't 'Ready'")
    args = parser.parse_args()

    if args.all_ready:
        succ, fail_n = run_all_ready()
        print(f"Done: {succ} succeeded, {fail_n} failed.")
        sys.exit(0 if fail_n == 0 else 1)
    ok, msg = run_caption(args.number, force=args.force)
    print(("SUCCESS: " if ok else "FAILED: ") + msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
