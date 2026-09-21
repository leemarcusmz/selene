#!/usr/bin/env python3
# =============================================================================
# Selene Dreams — Append a new row to the Generation Queue
# =============================================================================
# Called by the Cowork prompt-writer skill after the user approves generated
# prompts. Writes a fresh row to the next empty position in the sheet with
# Year, Month, Fabric, Product Type, Variant, and up to 5 prompts.
#
# 2026-08-17: per-row cap raised back to 5 — the sheet's own column count.
# Credit control moved to WEEKLY_IMAGE_CAP in picker.gs (15 images/week), so
# limiting each row separately just forced good slides to be discarded.
# 2026-07-20 (superseded): hard cap lowered from 5 to 3 prompts per row to save
# generation credits (the sheet still has Prompt 1-5 columns; Prompt 4-5
# are always left blank). Override requires --allow-extra.
#
# Usage:
#   python3 append_row.py \
#       --fabric "Silk" \
#       --product-type "Pillow Case" \
#       --variant "Alabaster White" \
#       --year 2026 \
#       --month July \
#       --prompts '[{"prompt":"Scene 1..."},{"prompt":"Scene 2..."}]'
#
# The Status column is left blank so the user can review the row in the
# sheet before flipping Status to Ready to trigger image generation.
# =============================================================================

import argparse
import json
import sys
from datetime import datetime

import config
from google_services import get_google_services


def find_first_empty_row(sheet, start_row=2):
    """
    Return the sheet-row index (1-based) of the first row that is truly
    empty - i.e. Year, Fabric AND Prompt 1 are all blank.

    Patched 2026-07-18: keying on Year alone caused draft rows (prompts
    parked in the sheet without Year/Month filled in) to be treated as
    empty and OVERWRITTEN by the next append. A row now counts as occupied
    if any of the three anchor columns has content.
    """
    year_vals = sheet.col_values(config.COL_YEAR + 1)
    fabric_vals = sheet.col_values(config.COL_FABRIC + 1)
    prompt1_vals = sheet.col_values(config.PROMPT_COLS[0] + 1)

    def cell(vals, i):
        return vals[i - 1] if i <= len(vals) else ""

    last = max(len(year_vals), len(fabric_vals), len(prompt1_vals))
    for i in range(start_row, last + 1):
        occupied = any(
            str(cell(vals, i)).strip()
            for vals in (year_vals, fabric_vals, prompt1_vals)
        )
        if not occupied:
            return i
    # If no empty row found within existing data, append at the end
    return last + 1


def main():
    parser = argparse.ArgumentParser(description="Append a Selene Dreams generation row")
    parser.add_argument("--fabric", required=True)
    parser.add_argument("--product-type", required=True)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--year", default=str(datetime.now().year))
    parser.add_argument("--month", default=datetime.now().strftime("%B"))
    parser.add_argument(
        "--prompts",
        required=True,
        help='JSON array of prompt objects, e.g. \'[{"prompt":"..."}]\'',
    )
    parser.add_argument(
        "--allow-extra",
        action="store_true",
        help="Deprecated — the per-row cap is now 5, the sheet's own limit.",
    )
    args = parser.parse_args()

    # Parse prompts JSON — accept either [{"prompt": "..."}] or ["...", "..."]
    try:
        raw = json.loads(args.prompts)
    except json.JSONDecodeError as e:
        print(f"ERROR: --prompts is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    prompts = []
    for item in raw:
        if isinstance(item, dict) and "prompt" in item:
            prompts.append(item["prompt"])
        elif isinstance(item, str):
            prompts.append(item)
        else:
            print(f"ERROR: unrecognized prompt item shape: {item}", file=sys.stderr)
            sys.exit(1)

    if len(prompts) > 5:
        print("ERROR: max 5 prompts per row (sheet only has Prompt 1-5)", file=sys.stderr)
        sys.exit(1)
    if len(prompts) > 5 and not args.allow_extra:
        print(
            "ERROR: max 5 prompts per row — a row has exactly five Prompt "
            "columns (cap raised from 3 on 2026-08-17; the credit ceiling is "
            "now the weekly image cap in picker.gs, not a per-row limit).",
            file=sys.stderr,
        )
        sys.exit(1)
    if not prompts:
        print("ERROR: at least one prompt required", file=sys.stderr)
        sys.exit(1)

    # Pad to 5 so we always write the same number of columns
    prompts_padded = prompts + [""] * (5 - len(prompts))

    print("Connecting to Google Sheets...")
    sheets_client, _ = get_google_services()
    spreadsheet = sheets_client.open_by_key(config.GOOGLE_SHEET_ID)
    sheet = spreadsheet.worksheet(config.GOOGLE_SHEET_NAME)

    row = find_first_empty_row(sheet)
    print(f"Writing to row {row}...")

    # Build the row values in column order.
    # Only fill Year through Prompt 5 — leave Status blank so the user
    # reviews the row in the sheet before triggering image generation.
    sheet.update_cell(row, config.COL_YEAR + 1, args.year)
    sheet.update_cell(row, config.COL_MONTH + 1, args.month)
    sheet.update_cell(row, config.COL_FABRIC + 1, args.fabric)
    sheet.update_cell(row, config.COL_PRODUCT_TYPE + 1, args.product_type)
    sheet.update_cell(row, config.COL_VARIANT + 1, args.variant)
    for i, col in enumerate(config.PROMPT_COLS):
        sheet.update_cell(row, col + 1, prompts_padded[i])

    print(f"SUCCESS: Row {row} added.")
    print(
        f"  {args.fabric} / {args.product_type} / {args.variant} — "
        f"{args.month} {args.year}"
    )
    print(f"  {len(prompts)} prompt(s) written.")
    print(f"  Review the row, then flip its Status (col D) to 'Ready' on the "
          f"Generation Status tab to generate images.")


if __name__ == "__main__":
    main()
