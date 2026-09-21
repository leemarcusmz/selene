# =============================================================================
# Selene Dreams — Generation QA Runner v1.0 (2026-08-12)
# qa_runner.py — Score the GENERATED images, and tie the score to the prompt
# =============================================================================
#
# WHY THIS EXISTS: the visual screener judges reference images from other
# brands; nothing ever judged Selene's own generated output. The prompt runner
# was therefore the one stage in the pipeline that learned nothing — prompts
# went out, images came back, and no record connected the two.
#
# This runner closes that loop without needing any Instagram data. After a row
# generates successfully it:
#
#   1. Downloads the generated images from Drive and the prompts that made
#      them from the Generation Queue.
#   2. Views every image with the Claude Code CLI and scores it against
#      brand-guide.md's 12-point rubric — the SAME rubric the screener uses on
#      references, so scores are comparable across the pipeline.
#   3. Checks product fidelity (is this actually the stated fabric / product /
#      colourway?) and AI artifacts, which no other stage checks.
#   4. Fills in the "QA: pending" line of that row's prompt-playbook.md entry,
#      appends a row per image to generation-scores.csv, and pushes.
#   5. Writes a one-line summary into Generation Status col M so the score is
#      visible in the sheet without opening GitHub.
#
# Fired automatically by server.py after a successful image generation.
#
# CLI usage:
#   python3 qa_runner.py --number 14
# =============================================================================

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

import config
import pipeline_state
from google_services import (
    get_google_services,
    download_file_from_drive,
    get_gs_sheet,
    find_gs_row,
    gs_append_remark,
)
from caption_runner import (
    clone_memory,
    invoke_claude_json,
    load_prompt,
    log,
    extract_drive_ids,
)

QA_SCHEMA = {
    "images": {"type": "list", "min_len": 1},
    "carouselCoherence": {"type": "str", "required": False},
    "promptLearning": {"type": "str", "required": False},
    "verdict": {"type": "str", "required": False},
}

PLAYBOOK_FILE = "prompt-playbook.md"
SCORES_CSV = "generation-scores.csv"
CSV_HEADER = ["date", "row", "fabric", "productType", "variant", "image",
              "score", "fidelity", "flags", "rationale"]

# =============================================================================
# MEMORY WRITES
# =============================================================================

def update_playbook(mem_dir, number, result, avg):
    """Replace the '- QA: pending' line of ROW {number}'s playbook entry with
    the real QA outcome. Falls back to appending if the anchor is missing."""
    path = os.path.join(mem_dir, PLAYBOOK_FILE)
    scores = result.get("images", [])
    qa_lines = [
        f"- QA: avg {avg:.1f}/12 · verdict {result.get('verdict','?')} · "
        f"coherence {result.get('carouselCoherence','?')}",
    ]
    for s in scores:
        flags = str(s.get("flags", "")).strip()
        qa_lines.append(
            f"  - img {s.get('i')}: {s.get('score')}/12 · fidelity "
            f"{s.get('fidelity','?')}"
            + (f" · FLAG: {flags}" if flags else "")
            + f" — {s.get('rationale','')}")
    if result.get("promptLearning"):
        qa_lines.append(f"- PROMPT LEARNING: {result['promptLearning']}")
    qa_lines.append(f"- QA prompt version: {result.get('_promptVersion', '?')}")
    block = "\n".join(qa_lines)

    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write("# Selene Prompt Playbook\n")
    with open(path) as f:
        lines = f.read().split("\n")

    anchor = f"### ROW {number} "
    start = next((i for i, l in enumerate(lines) if l.startswith(anchor)), None)
    if start is not None:
        for i in range(start, len(lines)):
            if lines[i].startswith("### ") and i > start:
                break
            if lines[i].strip() == "- QA: pending":
                lines[i] = block
                with open(path, "w") as f:
                    f.write("\n".join(lines))
                return
    # No anchor (row created before the playbook existed, or already scored)
    with open(path, "a") as f:
        f.write(f"\n### QA ROW {number} · {datetime.now().strftime('%Y-%m-%d')} "
                f"(no matching prompt entry)\n{block}\n")


def append_scores_csv(mem_dir, number, fabric, product_type, variant, result):
    path = os.path.join(mem_dir, SCORES_CSV)
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(CSV_HEADER)
        today = datetime.now().strftime("%Y-%m-%d")
        for s in result.get("images", []):
            w.writerow([today, number, fabric, product_type, variant,
                        s.get("i"), s.get("score"), s.get("fidelity"),
                        str(s.get("flags", "")).replace("\n", " "),
                        str(s.get("rationale", "")).replace("\n", " ")])


def push_memory(mem_dir, number):
    pipeline_state.mirror_to_memory(mem_dir)
    ok, msg = pipeline_state.push_with_retry(
        mem_dir, f"Generation QA row #{number}", logger=log)
    log(f"  QA results pushed to memory ({msg})." if ok
        else f"  NOTE: QA push failed ({msg}) — scores are still in the "
             f"sheet remark.")


# =============================================================================
# CORE
# =============================================================================

def run_qa(number, sheets_client=None, drive_service=None):
    """Score the generated images for queue row #number. Returns (ok, msg).
    Never raises into the caller — QA is an observer, it must not be able to
    break a generation that already succeeded."""
    with pipeline_state.stage(pipeline_state.QA, row=number) as st:
        return pipeline_state.finish(
            _run_qa(number, sheets_client, drive_service), st)


def _run_qa(number, sheets_client=None, drive_service=None):
    log(f"Generation QA for #{number}...")
    try:
        if sheets_client is None or drive_service is None:
            sheets_client, drive_service = get_google_services()
        spreadsheet = sheets_client.open_by_key(config.GOOGLE_SHEET_ID)
        queue = spreadsheet.worksheet(config.GOOGLE_SHEET_NAME)

        row = queue.row_values(number + 1)
        while len(row) < config.TOTAL_COLS:
            row.append("")
        fabric = row[config.COL_FABRIC].strip()
        product_type = row[config.COL_PRODUCT_TYPE].strip()
        variant = row[config.COL_VARIANT].strip()
        prompts = [row[c].strip() for c in config.PROMPT_COLS if row[c].strip()]
        image_ids = extract_drive_ids(row[config.COL_IMAGE_URLS])
        if not image_ids:
            return False, "no Image URLs on the row — nothing to score"

        workdir = tempfile.mkdtemp(prefix=f"selene_qa_{number}_")
        try:
            img_dir = os.path.join(workdir, "images")
            os.makedirs(img_dir)
            for i, fid in enumerate(image_ids, 1):
                data = download_file_from_drive(drive_service, fid)
                with open(os.path.join(img_dir, f"image_{i:02d}.png"), "wb") as f:
                    f.write(data)

            mem = clone_memory(workdir)
            if not mem:
                return False, ("memory repo unavailable — QA needs brand-guide.md "
                               "for the rubric")

            prompt_block = "\n".join(
                f"{i}. {p}" for i, p in enumerate(prompts, 1)) or "(none recorded)"
            out_path = os.path.join(workdir, "qa.json")
            template, qa_version = load_prompt("generation-qa")
            prompt = template.format(
                mem=mem, fabric=fabric, product_type=product_type,
                variant=variant, prompt_block=prompt_block, img_dir=img_dir,
                n_images=len(image_ids), out_path=out_path)
            log(f"  Scoring {len(image_ids)} generated image(s) "
                f"(prompt {qa_version})...")
            ok, result = invoke_claude_json(
                prompt, workdir, out_path, schema=QA_SCHEMA, stage="qa",
                timeout=1200)
            if not ok:
                return False, result
            result["_promptVersion"] = qa_version

            scores = [s for s in result.get("images", [])
                      if isinstance(s.get("score"), (int, float))]
            if not scores:
                return False, "QA returned no usable scores"
            avg = sum(s["score"] for s in scores) / len(scores)
            low = min(s["score"] for s in scores)
            off = [s["i"] for s in scores
                   if str(s.get("fidelity", "")).lower().startswith("off")]
            flagged = [s["i"] for s in scores if str(s.get("flags", "")).strip()]

            update_playbook(mem, number, result, avg)
            append_scores_csv(mem, number, fabric, product_type, variant, result)
            push_memory(mem, number)

            summary = (f"QA: avg {avg:.1f}/12 (low {low}) · "
                       f"{result.get('verdict','?')}")
            if off:
                summary += f" · PRODUCT DRIFT on img {', '.join(map(str, off))}"
            if flagged:
                summary += f" · flags on img {', '.join(map(str, flagged))}"

            gs = get_gs_sheet(queue)
            if gs is not None:
                gs_row = find_gs_row(gs, number)
                gs_append_remark(gs, gs_row, summary)
            log(f"  {summary}")
            return True, summary
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
    except Exception as e:
        log(f"  QA failed (non-fatal): {e}")
        return False, f"QA failed: {e}"


def main():
    parser = argparse.ArgumentParser(description="Selene generation QA runner")
    parser.add_argument("--number", type=int, required=True,
                        help="Queue # whose generated images should be scored")
    args = parser.parse_args()
    ok, msg = run_qa(args.number)
    print(("SUCCESS: " if ok else "FAILED: ") + msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
