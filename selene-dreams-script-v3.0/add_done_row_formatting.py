# =============================================================================
# Selene Dreams — Add "Done row" conditional formatting to the sheet
# =============================================================================
# Adds a conditional formatting rule that turns any row light green whenever
# Status (column Q) equals "Done". Works automatically regardless of whether
# you type "Done" manually or the Python server writes it via API.
#
# Run once:
#   python3 add_done_row_formatting.py
# =============================================================================

from datetime import datetime

import config
from google_services import get_google_services


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def main():
    log("Connecting to Google Sheets...")
    sheets_client, _ = get_google_services()
    spreadsheet = sheets_client.open_by_key(config.GOOGLE_SHEET_ID)
    sheet = spreadsheet.worksheet(config.GOOGLE_SHEET_NAME)
    sheet_id = sheet.id
    log(f"Opened '{spreadsheet.title}'.")

    # Q is the Status column (0-indexed 16). Formula uses $Q2 with the
    # relative-row anchor so it adjusts per row when applied to A2:V500.
    #
    # Light green fill: #D9EAD3 (Google's default "light green 3")
    request = {
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{
                    "sheetId": sheet_id,
                    "startRowIndex": 1,          # row 2 (0-indexed)
                    "endRowIndex": 500,
                    "startColumnIndex": 0,       # A
                    "endColumnIndex": config.TOTAL_COLS,   # through last column
                }],
                "booleanRule": {
                    "condition": {
                        "type": "CUSTOM_FORMULA",
                        "values": [{"userEnteredValue": '=$Q2="Done"'}],
                    },
                    "format": {
                        "backgroundColor": {
                            "red": 0.85, "green": 0.918, "blue": 0.827,
                        },
                    },
                },
            },
            "index": 0,
        }
    }

    log("Applying conditional formatting: green fill on rows where Status = 'Done'...")
    spreadsheet.batch_update({"requests": [request]})
    log("Done.")
    log("")
    log("Any existing Done rows should light up green immediately.")
    log("New Done rows (from the Python server or manual typing) will color themselves.")


if __name__ == "__main__":
    main()
