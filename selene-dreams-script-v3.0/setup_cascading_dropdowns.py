# =============================================================================
# Selene Dreams — Cascading dropdowns for Product Type and Variant
# =============================================================================
# Sets up dependent dropdowns:
#   - Product Type (column E) depends on Fabric (column D)
#   - Variant (column F) depends on Fabric + Product Type
#
# Also:
#   - Renames the source photo Silk_Eye-Mask_Oliver-Sage.jpg to Olive-Sage.jpg
#     inside 01. Product Photos in Drive.
#   - Fixes any "Oliver Sage" values in existing Variant cells.
#
# Auto-clearing when Fabric or Product Type changes is handled by the
# updated trigger.gs — you'll need to paste that into the Apps Script editor
# separately.
#
# Run once:
#   python3 setup_cascading_dropdowns.py
# =============================================================================

from datetime import datetime

import config
from google_services import get_google_services


# =============================================================================
# DATA — canonical fabric / product-type / variant mappings
# =============================================================================

FABRIC_TYPES = {
    "Cooling":  ["Blanket"],
    "Gauze":    ["Blanket"],
    "Linen":    ["Duvet Set", "Sheet Set"],
    "Percale":  ["Duvet Set", "Sheet Set"],
    "Sateen":   ["Duvet Set", "Sheet Set"],
    "Silk":     ["Eye Mask", "Pillow Case"],
    "Tencel":   ["Duvet Set", "Sheet Set"],
}

VARIANTS = {
    ("Cooling", "Blanket"):     ["Cream White", "Ocean Breeze", "Silver Mist"],
    ("Gauze",   "Blanket"):     ["Alabaster White", "Shadow Gray", "Soft Maple"],
    ("Linen",   "Duvet Set"):   ["Alabaster White", "Desert Sand", "Stone Sage", "Terracotta Blush"],
    ("Linen",   "Sheet Set"):   ["Alabaster White", "Desert Sand", "Stone Sage", "Terracotta Blush"],
    ("Percale", "Duvet Set"):   ["Ash Gray", "Desert Sand", "Herb Sage", "Icy White"],
    ("Percale", "Sheet Set"):   ["Ash Gray", "Desert Sand", "Herb Sage", "Icy White"],
    ("Sateen",  "Duvet Set"):   ["Driftwood", "Icy White", "Ocean Breeze"],
    ("Sateen",  "Sheet Set"):   ["Driftwood", "Icy White", "Ocean Breeze"],
    ("Silk",    "Eye Mask"):    ["Alabaster White", "Olive Sage", "Pewter Gray", "Warm Taupe"],
    ("Silk",    "Pillow Case"): ["Alabaster White", "Olive Sage", "Pewter Gray", "Warm Taupe"],
    ("Tencel",  "Duvet Set"):   ["Deep Ocean", "Dove Gray", "Frost White", "Stone Taupe"],
    ("Tencel",  "Sheet Set"):   ["Deep Ocean", "Dove Gray", "Frost White", "Stone Taupe"],
}

LOOKUP_SHEET = "Lookup"
VALIDATION_END_ROW = 500


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def clean_pt(pt):
    """Strip spaces from a product type — used for named-range name safety.
    E.g. 'Duvet Set' -> 'DuvetSet'."""
    return pt.replace(" ", "")


# =============================================================================
# STEP 1 — Rename Silk_Eye-Mask_Oliver-Sage.jpg in Drive (if uploaded)
# =============================================================================

def rename_oliver_sage_in_drive(drive_service):
    old_name = "Silk_Eye-Mask_Oliver-Sage.jpg"
    new_name = "Silk_Eye-Mask_Olive-Sage.jpg"

    query = (
        f"name='{old_name}' and "
        f"'{config.DRIVE_PRODUCT_PHOTOS_FOLDER_ID}' in parents and "
        f"trashed=false"
    )
    resp = drive_service.files().list(
        q=query, fields="files(id, name)",
        supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute()
    files = resp.get("files", [])

    if not files:
        log(f"  No file named '{old_name}' in 01. Product Photos — skipping Drive rename.")
        return

    for f in files:
        drive_service.files().update(
            fileId=f["id"], body={"name": new_name}, supportsAllDrives=True,
        ).execute()
        log(f"  Renamed in Drive: {old_name} -> {new_name}")


# =============================================================================
# STEP 2 — Fix "Oliver Sage" values in existing Variant cells
# =============================================================================

def fix_oliver_sage_in_sheet(sheet):
    all_rows = sheet.get_all_values()
    fixes = 0
    for i, row in enumerate(all_rows[1:], start=2):
        if len(row) <= config.COL_VARIANT:
            continue
        variant = row[config.COL_VARIANT].strip()
        if variant.lower() == "oliver sage":
            sheet.update_cell(i, config.COL_VARIANT + 1, "Olive Sage")
            fixes += 1
            log(f"  Row {i}: 'Oliver Sage' -> 'Olive Sage'")
    if not fixes:
        log("  No 'Oliver Sage' values found in sheet.")


# =============================================================================
# STEP 3 — Build the Lookup sheet and named ranges
# =============================================================================

def setup_lookup_and_validation(spreadsheet, gen_sheet):
    # Create or clear the Lookup tab
    try:
        lookup = spreadsheet.worksheet(LOOKUP_SHEET)
        log(f"  Found existing '{LOOKUP_SHEET}' tab — clearing.")
        lookup.clear()
    except Exception:
        log(f"  Creating '{LOOKUP_SHEET}' tab.")
        lookup = spreadsheet.add_worksheet(title=LOOKUP_SHEET, rows=50, cols=30)

    lookup.resize(rows=50, cols=30)

    # -------------------------------------------------------------------
    # Section 1 — Product Types per Fabric
    # Layout:
    #   Row 1:  header ("Product Types" | Cooling | Gauze | Linen | ...)
    #   Row 2+: product types stacked vertically under each fabric column
    # -------------------------------------------------------------------
    fabrics = list(FABRIC_TYPES.keys())
    header_row = ["Product Types"] + fabrics
    lookup.update("A1", [header_row])

    max_pt = max(len(t) for t in FABRIC_TYPES.values())
    for col_idx, fabric in enumerate(fabrics):
        col_letter = chr(ord("B") + col_idx)
        types = FABRIC_TYPES[fabric]
        lookup.update(
            f"{col_letter}2:{col_letter}{1 + len(types)}",
            [[t] for t in types],
        )

    # -------------------------------------------------------------------
    # Section 2 — Variants per (Fabric, Product Type)
    # Layout:
    #   Row 10: header row with combo keys like Cooling_Blanket, Gauze_Blanket, ...
    #   Row 11+: variants stacked vertically under each combo column
    # -------------------------------------------------------------------
    variant_header_row = 10
    combos = list(VARIANTS.keys())
    combo_headers = [f"{f}_{clean_pt(pt)}" for f, pt in combos]
    lookup.update(f"A{variant_header_row}", [combo_headers])

    for col_idx, combo in enumerate(combos):
        col_letter = chr(ord("A") + col_idx)
        variants = VARIANTS[combo]
        lookup.update(
            f"{col_letter}{variant_header_row + 1}:"
            f"{col_letter}{variant_header_row + len(variants)}",
            [[v] for v in variants],
        )

    log("  Lookup data written.")

    # -------------------------------------------------------------------
    # Named ranges + data validation via batchUpdate
    # -------------------------------------------------------------------
    lookup_id = lookup.id
    gen_id = gen_sheet.id

    # First delete any existing named ranges we're about to (re)create,
    # so re-runs don't error out with "already exists".
    existing_ranges = spreadsheet.list_named_ranges()
    names_to_delete = {r["name"] for r in existing_ranges
                       if r["name"].startswith(("Types_", "Variants_"))}
    delete_reqs = []
    for r in existing_ranges:
        if r["name"] in names_to_delete:
            delete_reqs.append(
                {"deleteNamedRange": {"namedRangeId": r["namedRangeId"]}}
            )
    if delete_reqs:
        spreadsheet.batch_update({"requests": delete_reqs})
        log(f"  Cleared {len(delete_reqs)} old named range(s).")

    # Now add fresh ranges + validation
    requests = []

    # Types_[Fabric] — vertical column under each fabric in Section 1
    for col_idx, fabric in enumerate(fabrics):
        types = FABRIC_TYPES[fabric]
        requests.append({
            "addNamedRange": {
                "namedRange": {
                    "name": f"Types_{fabric}",
                    "range": {
                        "sheetId": lookup_id,
                        "startRowIndex": 1,            # row 2 (0-indexed)
                        "endRowIndex": 1 + len(types),
                        "startColumnIndex": 1 + col_idx,   # B onwards
                        "endColumnIndex": 2 + col_idx,
                    }
                }
            }
        })

    # Variants_[Fabric]_[TypeNoSpace]
    for col_idx, (fabric, pt) in enumerate(combos):
        variants = VARIANTS[(fabric, pt)]
        requests.append({
            "addNamedRange": {
                "namedRange": {
                    "name": f"Variants_{fabric}_{clean_pt(pt)}",
                    "range": {
                        "sheetId": lookup_id,
                        "startRowIndex": variant_header_row,           # 0-indexed row 11
                        "endRowIndex": variant_header_row + len(variants),
                        "startColumnIndex": col_idx,                   # A onwards
                        "endColumnIndex": col_idx + 1,
                    }
                }
            }
        })

    # Cascading data validation
    # NOTE: $D2 is a relative-row reference — Sheets adjusts it per row.
    requests.append({
        "setDataValidation": {
            "range": {
                "sheetId": gen_id,
                "startRowIndex": 1,
                "endRowIndex": VALIDATION_END_ROW,
                "startColumnIndex": config.COL_PRODUCT_TYPE,
                "endColumnIndex": config.COL_PRODUCT_TYPE + 1,
            },
            "rule": {
                "condition": {
                    "type": "ONE_OF_RANGE",
                    "values": [{"userEnteredValue": '=INDIRECT("Types_"&$D2)'}],
                },
                "showCustomUi": True,
                "strict": True,
                "inputMessage": "Pick a Product Type (depends on Fabric)",
            }
        }
    })

    requests.append({
        "setDataValidation": {
            "range": {
                "sheetId": gen_id,
                "startRowIndex": 1,
                "endRowIndex": VALIDATION_END_ROW,
                "startColumnIndex": config.COL_VARIANT,
                "endColumnIndex": config.COL_VARIANT + 1,
            },
            "rule": {
                "condition": {
                    "type": "ONE_OF_RANGE",
                    "values": [{
                        "userEnteredValue":
                            '=INDIRECT("Variants_"&$D2&"_"&SUBSTITUTE($E2," ",""))'
                    }],
                },
                "showCustomUi": True,
                "strict": True,
                "inputMessage": "Pick a Variant (depends on Fabric and Product Type)",
            }
        }
    })

    # Hide the Lookup tab so users don't accidentally mess with it
    requests.append({
        "updateSheetProperties": {
            "properties": {"sheetId": lookup_id, "hidden": True},
            "fields": "hidden",
        }
    })

    spreadsheet.batch_update({"requests": requests})
    log("  Named ranges, validation rules, and tab-hide applied.")


# =============================================================================
# MAIN
# =============================================================================

def main():
    log("Connecting to Google services...")
    sheets_client, drive_service = get_google_services()
    spreadsheet = sheets_client.open_by_key(config.GOOGLE_SHEET_ID)
    gen_sheet = spreadsheet.worksheet(config.GOOGLE_SHEET_NAME)
    log(f"Opened '{spreadsheet.title}'.")
    print()

    log("Step 1/3 — Rename Oliver Sage in Drive (if present)...")
    rename_oliver_sage_in_drive(drive_service)
    print()

    log("Step 2/3 — Fix 'Oliver Sage' cells in the sheet...")
    fix_oliver_sage_in_sheet(gen_sheet)
    print()

    log("Step 3/3 — Build Lookup tab and apply cascading validation...")
    setup_lookup_and_validation(spreadsheet, gen_sheet)
    print()

    log("Done.")
    log("")
    log("Next step: paste the updated trigger.gs into your Apps Script editor")
    log("to enable auto-clearing of Product Type and Variant when Fabric changes.")


if __name__ == "__main__":
    main()
