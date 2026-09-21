# =============================================================================
# Selene Dreams — Baseline dropdowns for Product Type and Variant
# =============================================================================
# Adds a "fallback" static dropdown to every row in Product Type (E) and
# Variant (F), so the dropdown arrow shows on all rows — not just rows
# where a Fabric has been picked and Apps Script has set a filtered rule.
#
# When a user picks a Fabric, the existing Apps Script (trigger.gs)
# overrides that row's E and F validations with the fabric-specific
# filtered ranges. This baseline only shows before Fabric is picked, or
# after Fabric is cleared.
#
# Run once:
#   python3 add_baseline_dropdowns.py
# =============================================================================

from datetime import datetime

import config
from google_services import get_google_services


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

VALIDATION_END_ROW = 500


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def main():
    all_types = sorted({pt for pts in FABRIC_TYPES.values() for pt in pts})
    all_variants = sorted({v for vs in VARIANTS.values() for v in vs})

    log(f"Baseline Product Types ({len(all_types)}): {', '.join(all_types)}")
    log(f"Baseline Variants     ({len(all_variants)}): {', '.join(all_variants)}")
    print()

    log("Connecting to Google services...")
    sheets_client, _ = get_google_services()
    spreadsheet = sheets_client.open_by_key(config.GOOGLE_SHEET_ID)
    gen_sheet = spreadsheet.worksheet(config.GOOGLE_SHEET_NAME)
    gen_id = gen_sheet.id
    log(f"Opened '{spreadsheet.title}'.")

    requests = [
        {
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
                        "type": "ONE_OF_LIST",
                        "values": [{"userEnteredValue": t} for t in all_types],
                    },
                    "showCustomUi": True,
                    "strict": True,
                    "inputMessage": "Pick a Product Type (filtered by Fabric)",
                }
            }
        },
        {
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
                        "type": "ONE_OF_LIST",
                        "values": [{"userEnteredValue": v} for v in all_variants],
                    },
                    "showCustomUi": True,
                    "strict": True,
                    "inputMessage": "Pick a Variant (filtered by Fabric + Product Type)",
                }
            }
        },
    ]

    log("Applying baseline dropdowns to E2:E500 and F2:F500...")
    spreadsheet.batch_update({"requests": requests})
    log("Done.")
    log("")
    log("Every row will now show a dropdown arrow on Product Type and Variant.")
    log("Rows without a Fabric show all 5 / 20 options.")
    log("Rows with a Fabric picked show only the filtered options (via Apps Script).")


if __name__ == "__main__":
    main()
