# =============================================================================
# Selene Dreams — Image Generation Script v3.0
# generate.py — Core generation logic
# =============================================================================
#
# Reads rows from the Generation Queue sheet and produces images via FLUX 2
# Pro on Replicate. Designed to be called by server.py (webhook) or run
# directly from the CLI.
#
# CLI usage:
#   python generate.py
#     Processes all rows with Status = "Ready" matching the current month/year.
# =============================================================================

import time
from datetime import datetime

import config
from google_services import (
    get_google_services,
    get_or_create_year_month_folder,
    get_or_create_folder,
    find_source_image,
    download_file_from_drive,
    upload_file_to_drive,
    get_numbered_month,
    get_ready_rows,
    update_sheet_success,
    update_sheet_error,
    gs_get_gen_status,
    gs_set_gen_status,
)
from replicate_service import generate_image_with_flux


# =============================================================================
# HELPERS
# =============================================================================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def _dashify(s):
    return s.strip().replace(" ", "-")


def build_carousel_id(fabric, product_type, variant, month, year):
    """Cooling_Blanket_Cream-White_May2026"""
    return (
        f"{_dashify(fabric)}_{_dashify(product_type)}_"
        f"{_dashify(variant)}_{month}{year}"
    )


def build_image_filename(fabric, product_type, variant, month, year, index):
    """Cooling_Blanket_Cream-White_May_2026_01.png"""
    return (
        f"{_dashify(fabric)}_{_dashify(product_type)}_"
        f"{_dashify(variant)}_{month}_{year}_{index:02d}.png"
    )


# =============================================================================
# CORE
# =============================================================================

def process_row(row_index, sheet, drive_service):
    """
    Process a single sheet row.

    Sets status to Processing on entry to prevent duplicate webhook firings.
    On any failure, sets status to ERROR (not Ready) — this is the v3 fix
    for the v2 status-loop bug.
    """
    log(f"Fetching row {row_index}...")
    row = sheet.row_values(row_index)
    while len(row) < config.TOTAL_COLS:
        row.append("")

    # 2026-07-22: the control status lives ONLY in the Generation Status tab
    # (col D, keyed by # = queue row - 1) — the queue's Status column was
    # removed. If the tab is unreachable, we cannot verify Ready → skip.
    row_number = row_index - 1
    status = gs_get_gen_status(sheet, row_number)
    if status is None:
        msg = (f"Row {row_index}: Generation Status tab unreachable — "
               f"cannot verify Ready. Skipping.")
        log(msg)
        return False, msg
    if status != config.STATUS_READY:
        msg = f"Row {row_index} status is '{status}', not 'Ready'. Skipping."
        log(msg)
        return False, msg

    # Lock the row immediately (Generation Status col D — the queue's old
    # Status column was removed 2026-07-22)
    gs_set_gen_status(sheet, row_number, config.STATUS_PROCESSING)

    try:
        return _run_generation(row_index, row, sheet, drive_service)
    except Exception as e:
        msg = str(e)
        log(f"Unexpected error on row {row_index}: {msg}")
        update_sheet_error(sheet, row_index, f"Unexpected error: {msg}")
        return False, msg


def _run_generation(row_index, row, sheet, drive_service):
    # --- Read fields ---
    row_number_raw = row[config.COL_NUMBER].strip()
    try:
        row_number = int(row_number_raw)
    except ValueError:
        row_number = row_index - 1  # Fallback: data row position

    year = row[config.COL_YEAR].strip()
    month = row[config.COL_MONTH].strip()
    fabric = row[config.COL_FABRIC].strip()
    product_type = row[config.COL_PRODUCT_TYPE].strip()
    variant = row[config.COL_VARIANT].strip()

    # Validate the four required identifiers up front
    if not all([year, month, fabric, product_type, variant]):
        update_sheet_error(
            sheet, row_index,
            "Missing required field(s) — Year, Month, Fabric, Product Type, "
            "and Variant must all be filled.",
        )
        return False, "Missing required fields"

    if month not in ("January February March April May June July August "
                     "September October November December").split():
        update_sheet_error(
            sheet, row_index,
            f"Month '{month}' is not a valid month name. Use full English "
            f"month names (e.g. May, June)."
        )
        return False, f"Invalid month: {month}"

    prompts = [row[c].strip() for c in config.PROMPT_COLS]

    filled_prompts = [p for p in prompts if p]
    if not filled_prompts:
        update_sheet_error(
            sheet, row_index,
            "No prompts filled — at least one of Prompt 1..5 must contain "
            "text."
        )
        return False, "No prompts"

    log(
        f"Processing row {row_index} (#{row_number}): "
        f"{fabric} / {product_type} / {variant} — {month} {year}"
    )
    log(f"  Prompts to run: {len(filled_prompts)}")

    # --- Source image (with field-level error reporting) ---
    log("  Locating source image...")
    src_id, src_name, src_err = find_source_image(
        drive_service, fabric, product_type, variant
    )
    if not src_id:
        update_sheet_error(sheet, row_index, src_err["message"])
        return False, src_err["message"]
    log(f"  Source image: {src_name}")

    log("  Downloading source image...")
    product_bytes = download_file_from_drive(drive_service, src_id)

    # --- Generate ALL images first, in memory ---
    # 2026-07-22: the output folder is only created AFTER every prompt
    # succeeds, so failed runs leave no empty/partial "Row N" folders behind
    # (and no confusing _02/_03 duplicates from retries).
    generated_files = []   # (filename, bytes)
    cost_usd = 0.0

    for i, prompt in enumerate(prompts):
        if not prompt:
            continue  # blank prompt cells are skipped

        log(f"  Prompt {i + 1}/{len(prompts)}: generating...")
        try:
            generated = generate_image_with_flux(product_bytes, [], prompt)
        except Exception as e:
            update_sheet_error(
                sheet, row_index,
                f"Generation failed on prompt {i + 1}: {e}"
            )
            return False, str(e)

        if not generated:
            update_sheet_error(
                sheet, row_index,
                f"Model returned no image for prompt {i + 1}.",
            )
            return False, "Empty model response"

        filename = build_image_filename(
            fabric, product_type, variant, month, year, i + 1
        )
        generated_files.append((filename, generated))
        cost_usd += config.COST_PER_IMAGE_USD

        # Tiny pause to be polite on Replicate's side
        time.sleep(1)

    # --- All prompts succeeded: create the folder and upload ---
    month_folder_id = get_or_create_year_month_folder(
        drive_service, config.DRIVE_GENERATED_IMAGES_FOLDER_ID, year, month
    )
    row_folder_name = f"Row {row_number}"
    row_folder_id = get_or_create_folder(
        drive_service, row_folder_name, month_folder_id
    )
    log(f"  Output folder: {year}/{get_numbered_month(month)}/{row_folder_name}")

    image_urls = []
    for filename, data in generated_files:
        log(f"  Uploading: {filename}")
        image_urls.append(
            upload_file_to_drive(drive_service, data, filename, row_folder_id)
        )

    # --- Update sheet on success ---
    output_path = (
        f"{year}/{get_numbered_month(month)}/{row_folder_name}"
    )
    carousel_id = build_carousel_id(
        fabric, product_type, variant, month, year
    )
    update_sheet_success(
        sheet, row_index,
        credits_used=f"${cost_usd:.2f}",
        output_folder=output_path,
        image_urls=image_urls,
        carousel_id=carousel_id,
    )
    log(f"  Done. {len(image_urls)} image(s). ~${cost_usd:.2f}")

    # v14 auto-chain (2026-08-21): images are finished, so the caption follows
    # without waiting for a human to flip G. update_sheet_success ->
    # gs_mark_generation_done has already set G to Ready; this starts the run.
    # The sheet write alone would do nothing — on-edit triggers do not fire on
    # API writes. See chain.py.
    try:
        import chain
        if chain.fire_caption(row_number, queue_sheet=sheet):
            log(f"  → captioning #{row_number} now (auto-chain)")
        else:
            log(f"  → #{row_number} is caption-Ready but the run did not start; "
                f"see System Remark(s) on the row")
    except Exception as e:                      # never fail a good generation
        log(f"  NOTE: could not start the caption for #{row_number}: {e}")

    return True, f"Generated {len(image_urls)} image(s)"


# =============================================================================
# BATCH
# =============================================================================

def process_all_ready_rows(sheet, drive_service, filter_current_month=True):
    rows = get_ready_rows(sheet, filter_current_month=filter_current_month)
    if not rows:
        log("No Ready rows. Nothing to do.")
        return 0, 0
    log(f"Processing {len(rows)} row(s)...")
    succ, fail = 0, 0
    for row_index, _ in rows:
        ok, _ = process_row(row_index, sheet, drive_service)
        if ok:
            succ += 1
        else:
            fail += 1
        print()
    return succ, fail


# =============================================================================
# CLI
# =============================================================================

def main():
    print("=" * 60)
    print("Selene Dreams — Image Generation Script v3.0 (FLUX 2 Pro)")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    log("Connecting to Google services...")
    sheets, drive = get_google_services()
    sheet = sheets.open_by_key(config.GOOGLE_SHEET_ID).worksheet(
        config.GOOGLE_SHEET_NAME
    )
    log("Connected.")
    print()

    succ, fail = process_all_ready_rows(sheet, drive, filter_current_month=True)

    print("=" * 60)
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Results:  {succ} succeeded, {fail} failed (status set to ERROR)")
    print("=" * 60)


if __name__ == "__main__":
    main()
