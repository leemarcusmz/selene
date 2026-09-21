# =============================================================================
# Selene Dreams — Sheet Dropdowns Updater
# =============================================================================
# Adds data validation (dropdowns) to the Month and Fabric columns in the
# Generation Queue sheet, and normalizes any existing values so they match
# the dropdown options exactly.
#
# Run once:
#   python3 update_sheet_dropdowns.py
# =============================================================================

from datetime import datetime

import config
from google_services import get_google_services


MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

FABRICS = ["Cooling", "Gauze", "Linen", "Percale", "Sateen", "Silk", "Tencel"]

VALIDATION_RANGE_START = 2   # first data row (skip header)
VALIDATION_RANGE_END = 500   # far enough for future rows


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def normalize_from_list(value, valid_list):
    """Best-effort match of a user-typed value against a canonical list.

    Tries: exact, case-insensitive, first-three-char prefix.
    Returns the canonical form if found, or the original value if not.
    """
    if not value:
        return value
    v = value.strip()
    for canon in valid_list:
        if v.lower() == canon.lower():
            return canon
    # Prefix match — handles "Jan" -> "January", "coo" -> "Cooling"
    for canon in valid_list:
        if len(v) >= 3 and canon.lower().startswith(v.lower()[:3]):
            return canon
    return v


def main():
    log("Connecting to Google services...")
    sheets_client, _ = get_google_services()
    spreadsheet = sheets_client.open_by_key(config.GOOGLE_SHEET_ID)
    sheet = spreadsheet.worksheet(config.GOOGLE_SHEET_NAME)
    sheet_id = sheet.id
    log(f"Opened '{sheet.title}'.")

    # ------------------------------------------------------------------
    # Normalize existing Month and Fabric values
    # ------------------------------------------------------------------
    all_rows = sheet.get_all_values()
    if len(all_rows) <= 1:
        log("Sheet has no data rows yet — skipping value normalization.")
    else:
        month_updates = []
        fabric_updates = []

        for i, row in enumerate(all_rows[1:], start=2):
            # row index within all_rows list; sheet row = i (1-based)
            month_val = row[config.COL_MONTH] if len(row) > config.COL_MONTH else ""
            fabric_val = row[config.COL_FABRIC] if len(row) > config.COL_FABRIC else ""

            new_month = normalize_from_list(month_val, MONTHS)
            new_fabric = normalize_from_list(fabric_val, FABRICS)

            if new_month != month_val:
                month_updates.append((i, month_val, new_month))
                sheet.update_cell(i, config.COL_MONTH + 1, new_month)
            if new_fabric != fabric_val:
                fabric_updates.append((i, fabric_val, new_fabric))
                sheet.update_cell(i, config.COL_FABRIC + 1, new_fabric)

        if month_updates:
            log(f"Normalized {len(month_updates)} Month value(s):")
            for r, old, new in month_updates:
                log(f"  Row {r}: '{old}' -> '{new}'")
        else:
            log("No Month values needed normalization.")

        if fabric_updates:
            log(f"Normalized {len(fabric_updates)} Fabric value(s):")
            for r, old, new in fabric_updates:
                log(f"  Row {r}: '{old}' -> '{new}'")
        else:
            log("No Fabric values needed normalization.")

    # ------------------------------------------------------------------
    # Apply data validation (dropdowns)
    # ------------------------------------------------------------------
    log("Applying data validation on Month and Fabric columns...")

    requests = [
        # Month — column C (0-indexed 2)
        {
            "setDataValidation": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": VALIDATION_RANGE_START - 1,
                    "endRowIndex": VALIDATION_RANGE_END,
                    "startColumnIndex": config.COL_MONTH,
                    "endColumnIndex": config.COL_MONTH + 1,
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": [{"userEnteredValue": m} for m in MONTHS],
                    },
                    "showCustomUi": True,
                    "strict": True,
                    "inputMessage": "Pick a month",
                },
            }
        },
        # Fabric — column D (0-indexed 3)
        {
            "setDataValidation": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": VALIDATION_RANGE_START - 1,
                    "endRowIndex": VALIDATION_RANGE_END,
                    "startColumnIndex": config.COL_FABRIC,
                    "endColumnIndex": config.COL_FABRIC + 1,
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": [{"userEnteredValue": f} for f in FABRICS],
                    },
                    "showCustomUi": True,
                    "strict": True,
                    "inputMessage": "Pick a fabric",
                },
            }
        },
    ]

    spreadsheet.batch_update({"requests": requests})
    log("Dropdowns applied.")
    log("")
    log("Done. Open the Sheet and click any Month or Fabric cell to see the dropdown.")


if __name__ == "__main__":
    main()
