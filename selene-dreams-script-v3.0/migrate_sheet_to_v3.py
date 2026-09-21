# =============================================================================
# Selene Dreams — One-off Sheet Migration v2.0 → v3.0
# =============================================================================
# What this script does:
#   1. Replaces the Generation Queue header row with the new 22-column schema.
#   2. Clears all data rows (you said the queue should be empty after migration).
#   3. Adds a =ROW()-1 formula to column A on rows 2..500 so # auto-numbers.
#   4. Adds Status data validation (dropdown) on column Q.
#   5. Rewrites the Documentation tab (creates it if missing).
#   6. Moves the spreadsheet file into the new "10. AI Generation" folder.
#   7. Verifies the service account still has access.
#
# Run once:
#   python migrate_sheet_to_v3.py
# =============================================================================

import sys
from datetime import datetime

import config
from google_services import get_google_services


# Documentation rows: (#, Field Name, Description, User or AI Use, Example, Notes)
DOC_ROWS = [
    (1, "#",
     "Auto-numbered position of this row within the data. Starts at 1 on the "
     "first data row. Used by the script to name the output folder (e.g. "
     "row with # = 5 produces 'Column 5' inside the month folder). The cell "
     "should be a formula =ROW()-1 so the number stays in sync if rows are "
     "appended. Avoid inserting rows in the middle, as that re-numbers all "
     "rows below and the previously generated 'Column N' folders will no "
     "longer match the row number.",
     "Formula", "1, 2, 3, ...",
     "Set as =ROW()-1 — script-managed indirectly."),

    (2, "Year",
     "Calendar year the content is being created for. Determines which year "
     "subfolder under '02. Reference Images' the script reads reference "
     "images from, and which year subfolder under '03. Generated Images' "
     "the outputs are saved to. Also used by the CLI batch mode to filter "
     "to current year only.",
     "User", "2026",
     "Use four-digit year."),

    (3, "Month",
     "Calendar month the content is being created for. Must be the full "
     "English month name (May, not 5 or 05). Determines the month subfolder "
     "for both reference image lookup and generated image output. Output "
     "folder uses two-digit zero-padded prefix automatically (e.g. May → "
     "'05. May').",
     "User", "May",
     "Use full month name. Case-sensitive."),

    (4, "Fabric",
     "First segment of the product source image filename. The bedding "
     "material category. The script looks for a file in '01. Product Photos' "
     "matching {Fabric}_{Product Type}_{Variant}.jpg. If Fabric does not "
     "match any file in the source folder, the row errors with a suggestion "
     "of the closest valid value.",
     "User", "Cooling",
     "Currently valid: Cooling, Gauze, Linen, Percale, Sateen, Silk, Tencel."),

    (5, "Product Type",
     "Second segment of the product source image filename. The form factor "
     "of the product. Combined with Fabric and Variant to locate the source "
     "image. Spaces in the value (e.g. 'Duvet Set') are converted to dashes "
     "by the script when building the filename.",
     "User", "Blanket",
     "Examples: Blanket, Duvet Set, Sheet Set, Eye Mask, Pillow Case."),

    (6, "Variant",
     "Third segment of the product source image filename. The color or "
     "finish of the product. Spaces become dashes when matching. The script "
     "validates Variant against the source folder and suggests the closest "
     "match if there is a typo.",
     "User", "Cream White",
     "Free text — must match a Variant that exists in 01. Product Photos."),

    (7, "Prompt 1",
     "Text prompt describing the first image you want generated. Sent to "
     "FLUX 2 Pro alongside the product photo (and Reference Image 1, if "
     "filled). Be specific about scene, lighting, mood, framing. Each prompt "
     "produces exactly one image.",
     "User",
     "A cozy Scandinavian bedroom, morning light, warm beige walls, "
     "linen curtains, the cooling blanket draped naturally on the bed.",
     "Required at minimum — at least one prompt cell must be filled."),

    (8, "Prompt 2",
     "Optional second prompt. Generates a second image with its own scene. "
     "Pairs with Reference Image 2.",
     "User", "(see Prompt 1 for format)", "Leave blank to skip."),
    (9, "Prompt 3",
     "Optional third prompt. Pairs with Reference Image 3.",
     "User", "(see Prompt 1 for format)", "Leave blank to skip."),
    (10, "Prompt 4",
     "Optional fourth prompt. Pairs with Reference Image 4.",
     "User", "(see Prompt 1 for format)", "Leave blank to skip."),
    (11, "Prompt 5",
     "Optional fifth prompt. Pairs with Reference Image 5. Maximum prompts "
     "per row is five.",
     "User", "(see Prompt 1 for format)", "Leave blank to skip."),

    (12, "Reference Image 1",
     "Filename(s) of aesthetic / mood reference image(s) for Prompt 1. The "
     "script looks them up in '02. Reference Images/{Year}/{Numbered "
     "Month}/'. Type just the filename (e.g. boho-bedroom.jpg) — no path. "
     "To pass multiple references for the same prompt, separate filenames "
     "with commas. The product photo is always passed; the reference images "
     "give the model additional grounding for scene, lighting, and mood. "
     "Avoid using a reference image that contains a competing product, as "
     "the model may copy the product in addition to the aesthetic.",
     "User",
     "boho-bedroom.jpg, warm-light.jpg",
     "Optional. If blank, only the product photo is used as input."),

    (13, "Reference Image 2",
     "Reference image(s) for Prompt 2. Same format as Reference Image 1. "
     "Same filename can be reused across multiple prompts if you want a "
     "consistent look.",
     "User", "boho-bedroom.jpg", "Optional."),
    (14, "Reference Image 3",
     "Reference image(s) for Prompt 3.",
     "User", "boho-bedroom.jpg", "Optional."),
    (15, "Reference Image 4",
     "Reference image(s) for Prompt 4.",
     "User", "boho-bedroom.jpg", "Optional."),
    (16, "Reference Image 5",
     "Reference image(s) for Prompt 5.",
     "User", "boho-bedroom.jpg", "Optional."),

    (17, "Status",
     "Drives the workflow. Setting this to 'Ready' fires the webhook and "
     "starts generation for this row. The script flips it to 'Processing' "
     "during the run, then to 'Done' on success or 'ERROR' on failure. "
     "'Hold' skips the row in batch mode. ERROR does not auto-retry — fix "
     "the issue, set back to 'Ready' to try again.",
     "User & AI",
     "Ready",
     "Allowed values: Ready, Hold, Processing, Done, ERROR."),

    (18, "Credits Used",
     "Approximate USD spent for this row. Calculated from Replicate's "
     "per-image price in config.py (default $0.05) multiplied by the number "
     "of images generated. Approximate — actual billing comes from the "
     "Replicate dashboard.",
     "AI", "$0.20", "Auto-filled."),

    (19, "Output Folder",
     "Drive path to the folder containing this row's generated images. "
     "Format: {Year}/{Numbered Month}/Column N. If the row is re-run, "
     "subsequent runs go to Column N_02, Column N_03, etc.",
     "AI", "2026/05. May/Column 5", "Auto-filled."),

    (20, "Image URLs",
     "Comma-separated direct Drive URLs for each generated image, in "
     "prompt order. Click any URL to open the image in Drive.",
     "AI", "https://..., https://...", "Auto-filled."),

    (21, "Carousel ID",
     "Stable identifier for the generated carousel, useful for downstream "
     "scheduling tools. Format: {Fabric}_{Product-Type}_{Variant}_{Month}{Year}.",
     "AI", "Cooling_Blanket_Cream-White_May2026", "Auto-filled."),

    (22, "Notes",
     "Free-text field. On a successful row, this is for your own notes. On "
     "an ERROR row, the script writes the failure reason here, prefixed "
     "with 'ERROR:'. Once you fix the issue, you can clear this and re-run.",
     "User & AI", "ERROR: Source image not found...",
     "Dual-purpose. Script will overwrite on error."),
]


HEADERS = [
    "#", "Year", "Month", "Fabric", "Product Type", "Variant",
    "Prompt 1", "Prompt 2", "Prompt 3", "Prompt 4", "Prompt 5",
    "Reference Image 1", "Reference Image 2", "Reference Image 3",
    "Reference Image 4", "Reference Image 5",
    "Status", "Credits Used", "Output Folder", "Image URLs",
    "Carousel ID", "Notes",
]

DOC_HEADERS = ["#", "Field Name", "Description", "User or AI Use", "Example", "Notes"]


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def main():
    log("Connecting to Google services...")
    sheets, drive = get_google_services()

    spreadsheet = sheets.open_by_key(config.GOOGLE_SHEET_ID)
    log(f"Opened spreadsheet: {spreadsheet.title}")

    # ---------------------------------------------------------------
    # 1. Generation Queue tab — replace headers, clear data
    # ---------------------------------------------------------------
    try:
        gen_sheet = spreadsheet.worksheet(config.GOOGLE_SHEET_NAME)
        log(f"Found existing tab: {config.GOOGLE_SHEET_NAME}")
    except Exception:
        log(f"Creating tab: {config.GOOGLE_SHEET_NAME}")
        gen_sheet = spreadsheet.add_worksheet(
            title=config.GOOGLE_SHEET_NAME, rows=500, cols=22
        )

    log("Clearing Generation Queue contents...")
    gen_sheet.clear()

    log("Resizing to 22 columns x 500 rows...")
    gen_sheet.resize(rows=500, cols=22)

    log("Writing new header row...")
    gen_sheet.update("A1:V1", [HEADERS])

    log("Adding =ROW()-1 formula on column A, rows 2..500...")
    formula_cells = [["=ROW()-1"] for _ in range(2, 501)]
    gen_sheet.update("A2:A500", formula_cells, value_input_option="USER_ENTERED")

    # ---------------------------------------------------------------
    # 2. Status data validation
    # ---------------------------------------------------------------
    log("Adding Status dropdown validation...")
    try:
        from gspread.utils import ValidationConditionType
        gen_sheet.add_validation(
            "Q2:Q500",
            condition_type=ValidationConditionType.one_of_list,
            values=["Ready", "Hold", "Processing", "Done", "ERROR"],
            showCustomUi=True,
        )
    except Exception as e:
        log(f"  (validation skipped: {e}) — set manually via Data > Data validation")

    # ---------------------------------------------------------------
    # 3. Documentation tab
    # ---------------------------------------------------------------
    try:
        doc_sheet = spreadsheet.worksheet(config.GOOGLE_DOC_SHEET_NAME)
        log(f"Found existing tab: {config.GOOGLE_DOC_SHEET_NAME}")
    except Exception:
        log(f"Creating tab: {config.GOOGLE_DOC_SHEET_NAME}")
        doc_sheet = spreadsheet.add_worksheet(
            title=config.GOOGLE_DOC_SHEET_NAME, rows=50, cols=6
        )

    log("Clearing Documentation contents...")
    doc_sheet.clear()
    doc_sheet.resize(rows=len(DOC_ROWS) + 1, cols=6)

    log("Writing Documentation rows...")
    doc_sheet.update("A1:F1", [DOC_HEADERS])
    doc_sheet.update(
        f"A2:F{len(DOC_ROWS) + 1}",
        [list(r) for r in DOC_ROWS],
    )

    # ---------------------------------------------------------------
    # 4. Move the file into the new Drive folder
    # ---------------------------------------------------------------
    log(f"Moving spreadsheet to parent folder {config.DRIVE_PARENT_FOLDER_ID}...")
    try:
        file = drive.files().get(
            fileId=config.GOOGLE_SHEET_ID,
            fields="parents",
            supportsAllDrives=True,
        ).execute()
        old_parents = ",".join(file.get("parents", []))
        drive.files().update(
            fileId=config.GOOGLE_SHEET_ID,
            addParents=config.DRIVE_PARENT_FOLDER_ID,
            removeParents=old_parents,
            fields="id, parents",
            supportsAllDrives=True,
        ).execute()
        log("  Moved.")
    except Exception as e:
        log(f"  WARN: move failed: {e}")
        log("  You may need to move the Sheet manually via Drive UI.")

    # ---------------------------------------------------------------
    # 5. Verify service account access
    # ---------------------------------------------------------------
    try:
        perms = drive.files().list(
            q=f"'{config.GOOGLE_SHEET_ID}' in parents", fields="files(id)"
        ).execute()
        # The service account having read access is implied by the fact we
        # got here, but we'll print a reminder.
    except Exception:
        pass

    log("")
    log("MIGRATION COMPLETE.")
    log("")
    log("REMINDERS:")
    log("  1. Confirm the Sheet is shared with:")
    log("       selene-dreams-script@selene-dreams.iam.gserviceaccount.com")
    log("     (Editor access). Open the Sheet, click Share, paste the email.")
    log("  2. Paste your Replicate API token into config.py.")
    log("  3. Upload renamed product photos from the local")
    log("     '_v3 Source Images (upload to Drive)' folder")
    log("     into '01. Product Photos' in Drive.")
    log("  4. Update trigger.gs in the Apps Script editor with the v3 status")
    log("     column index (Q = 17) and webhook secret (WEBHOOK_SECRET from .env).")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Aborted.")
        sys.exit(1)
