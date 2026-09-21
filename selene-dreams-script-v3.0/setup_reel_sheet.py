"""
setup_reel_sheet.py — build the "Selene Dreams - Trial Reel" sheet
=============================================================================
VERSION 1.6 — 2026-09-16

WHAT IT DOES
    Creates the "Trial Reels" tab in the sheet, writes the header row, freezes
    it, bolds it, sets sensible column widths, wraps the long text columns, and
    tints the four MANUAL columns so it is obvious which ones the lane will
    never touch.

    Safe to re-run. It creates only what is missing and never deletes a row.

STATUS
    RUN SUCCESSFULLY on the Mac 2026-09-09: tab renamed Untitled -> Trial Reels,
    headers written, formatting applied. Safe to re-run at any time. Re-run it
    after upgrading to reel_sheet 2.1 to widen and re-tint the header row.

WHY THE SHEET ALREADY EXISTS
    It was created on 2026-09-09 in MARCUS'S OWN Drive and then shared with the
    service account as writer. That order matters: a sheet created BY the
    service account is owned by the service account, lives in a Drive nobody
    can browse, and never shows up in his Drive at all.

RUN IT
    cd .../selene-dreams-script-v3.0
    python3 setup_reel_sheet.py

CHANGELOG
    1.6  2026-09-16  RATING column W (tinted, 1-5 dropdown, not strict) and
                     the "Taste Notes" tab (Date | Note | Applies to | Seen).
                     Both feed reel_feedback.py. Safe to re-run: W is appended
                     at the end and the taste tab is created only if missing.
    1.5  2026-09-11  Closing blurb corrected. 1.4 widened the sheet and moved
                     the tint to column Q, but still PRINTED "Columns N-Q are
                     yours" — the script told Marcus the opposite of what it
                     had just done to his sheet. Caught on the first real run.
    1.4  2026-09-10  22 columns, not 17: the metrics readback (reel_metrics)
                     fills N-P and R-V. The manual tint therefore shrinks to
                     column Q alone — it used to cover everything from N
                     rightwards, which would now wrongly mark five auto-written
                     columns as "yours". Safe to re-run: it only reformats.
    1.3  2026-09-09  Builds the "Videos" control tab too, with yes/no dropdowns
                     on the two columns Marcus owns and a tint marking them as
                     his. Blank means "auto-detect", which is why the dropdown
                     allows an empty cell.
    1.2  2026-09-09  FIX: crashed on gspread 6 with
                     "'Client' object has no attribute 'auth'". gspread 6
                     removed Client.auth (the client now holds an http_client
                     instead). The service-account address is read straight out
                     of credentials.json now, which is version-independent and
                     cannot break on a future gspread bump.
    1.1  2026-09-09  ADOPT THE IMPORTED TAB. The sheet is created by CSV import
                     so its header row exists before this ever runs, and that
                     leaves the first tab named "Untitled". v1.0 would have
                     added a SECOND tab called "Trial Reels" and left the real
                     one orphaned. Now it renames a lone existing tab instead.
    1.0  2026-09-09  First build.
=============================================================================
"""

import json
import sys

import config
import reel_config
from reel_sheet import (HEADERS, WRITTEN_COLS, VIDEO_HEADERS, VIDEO_TAB,
                        VIDEO_USER_COLS, TASTE_TAB, TASTE_HEADERS)

# width in pixels, and whether the column wraps
COLUMN_SPEC = [
    ("#", 46, False),
    ("Published", 118, False),
    ("Video", 190, False),
    ("Variant", 64, False),
    ("Hook", 300, True),
    ("Hook pattern", 190, False),
    ("Evidence", 88, False),
    ("Mode", 82, False),
    ("Overlay", 170, False),
    ("Caption style", 120, False),
    ("Caption", 430, True),
    ("Hashtags", 240, True),
    ("Permalink", 230, False),
    ("Views", 74, False),
    ("Likes", 68, False),
    ("Comments", 84, False),
    ("Notes", 260, True),
    ("Reach", 78, False),
    ("Shares", 72, False),
    ("Saves", 68, False),
    ("Avg watch (s)", 100, False),
    ("Metrics read", 150, False),
    ("Rating", 70, False),
]

# The ONLY column the lane never writes. Everything else from N rightwards is
# filled in by reel_metrics as of reel_sheet 2.1.
MANUAL_COL = HEADERS.index("Notes")
RATING_COL = HEADERS.index("Rating")


def main():
    try:
        from google_services import get_sheets_client
    except Exception as e:
        print(f"Could not import google_services: {e}")
        return 1

    gc = get_sheets_client()
    # Read the address from the key file rather than off the client object:
    # gspread 6 dropped Client.auth, and this cannot break on a version bump.
    try:
        with open(config.CREDENTIALS_FILE) as fh:
            sa_email = json.load(fh).get("client_email", "(unknown)")
    except Exception:
        sa_email = "(could not read credentials.json)"
    print(f"Service account: {sa_email}")
    print(f"Sheet: {reel_config.REEL_SHEET_URL}\n")

    try:
        ss = gc.open_by_key(reel_config.REEL_SHEET_ID)
    except Exception as e:
        print(f"FAILED to open the sheet: {e}\n")
        print(f"If this is a permission error, share the sheet with")
        print(f"  {sa_email}")
        print("as EDITOR, then re-run.")
        return 1

    print(f"Opened: {ss.title}")

    tab = reel_config.REEL_SHEET_TAB
    sheets = ss.worksheets()
    try:
        ws = ss.worksheet(tab)
        print(f"Tab '{tab}' already exists — leaving its rows alone.")
    except Exception:
        # The CSV import leaves exactly one tab, named "Untitled" (or after the
        # file). ADOPT it rather than adding a second tab beside it — that
        # would orphan the header row already sitting in the imported one.
        if len(sheets) == 1:
            ws = sheets[0]
            old = ws.title
            ws.update_title(tab)
            print(f"Renamed the imported tab '{old}' -> '{tab}'.")
        else:
            ws = ss.add_worksheet(title=tab, rows=400, cols=len(HEADERS))
            print(f"Created tab '{tab}'.")

    # A tab built by an earlier version may be exactly as wide as its old
    # header; writing column W into a 22-column grid is refused outright.
    try:
        if ws.col_count < len(HEADERS):
            ws.add_cols(len(HEADERS) - ws.col_count)
            print(f"Widened the grid to {len(HEADERS)} columns.")
    except Exception as e:
        print(f"(could not check the grid width: {e})")
    ws.update(values=[HEADERS], range_name="A1",
              value_input_option="RAW")
    print(f"Header row written ({len(HEADERS)} columns).")

    sid = ws.id
    requests = [
        # freeze the header
        {"updateSheetProperties": {
            "properties": {"sheetId": sid,
                           "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount"}},
        # bold header on the brand's winter white
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.93, "green": 0.93, "blue": 0.91},
                "verticalAlignment": "MIDDLE"}},
            "fields": "userEnteredFormat(textFormat,backgroundColor,verticalAlignment)"}},
        # top-align every data row so long captions read from the top
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 1},
            "cell": {"userEnteredFormat": {"verticalAlignment": "TOP"}},
            "fields": "userEnteredFormat.verticalAlignment"}},
        # tint column W (Rating) and give it a 1-5 dropdown; blank stays legal
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 0,
                      "startColumnIndex": RATING_COL,
                      "endColumnIndex": RATING_COL + 1},
            "cell": {"userEnteredFormat": {
                "backgroundColor": {"red": 0.98, "green": 0.96, "blue": 0.90}}},
            "fields": "userEnteredFormat.backgroundColor"}},
        {"setDataValidation": {
            "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 400,
                      "startColumnIndex": RATING_COL,
                      "endColumnIndex": RATING_COL + 1},
            "rule": {
                "condition": {"type": "ONE_OF_LIST",
                              "values": [{"userEnteredValue": str(n)}
                                         for n in (1, 2, 3, 4, 5)]},
                "strict": False, "showCustomUi": True}}},
        # tint column Q (Notes) — the one column nothing automatic writes
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 0,
                      "startColumnIndex": MANUAL_COL,
                      "endColumnIndex": MANUAL_COL + 1},
            "cell": {"userEnteredFormat": {
                "backgroundColor": {"red": 0.98, "green": 0.96, "blue": 0.90}}},
            "fields": "userEnteredFormat.backgroundColor"}},
    ]

    for i, (_, width, wrap) in enumerate(COLUMN_SPEC):
        requests.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS",
                      "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": width}, "fields": "pixelSize"}})
        if wrap:
            requests.append({"repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": 1,
                          "startColumnIndex": i, "endColumnIndex": i + 1},
                "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}},
                "fields": "userEnteredFormat.wrapStrategy"}})

    ss.batch_update({"requests": requests})
    print("Formatting applied: frozen header, widths, wrapping, manual-column tint.")

    # Drop the default Sheet1 if it is empty and no longer needed.
    for w in ss.worksheets():
        if w.title == "Sheet1" and len(ss.worksheets()) > 1:
            if not any(any(c for c in row) for row in w.get_all_values()):
                ss.del_worksheet(w)
                print("Removed the empty default 'Sheet1'.")
            break

    # ── the control tab ────────────────────────────────────────────────────
    try:
        vws = ss.worksheet(VIDEO_TAB)
        print(f"Tab '{VIDEO_TAB}' already exists — leaving its rows alone.")
    except Exception:
        vws = ss.add_worksheet(title=VIDEO_TAB, rows=400,
                               cols=len(VIDEO_HEADERS))
        print(f"Created tab '{VIDEO_TAB}'.")

    vws.update(values=[VIDEO_HEADERS], range_name="A1",
               value_input_option="RAW")

    vid = vws.id
    vreq = [
        {"updateSheetProperties": {
            "properties": {"sheetId": vid,
                           "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount"}},
        {"repeatCell": {
            "range": {"sheetId": vid, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.93, "green": 0.93, "blue": 0.91}}},
            "fields": "userEnteredFormat(textFormat,backgroundColor)"}},
    ]
    widths = [260, 200, 130, 140, 100, 90, 120, 120, 110, 260]
    for i, w in enumerate(widths):
        vreq.append({"updateDimensionProperties": {
            "range": {"sheetId": vid, "dimension": "COLUMNS",
                      "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": w}, "fields": "pixelSize"}})

    for col in VIDEO_USER_COLS:
        # Tint the two columns Marcus owns, and give them a yes/no dropdown.
        vreq.append({"repeatCell": {
            "range": {"sheetId": vid, "startRowIndex": 0,
                      "startColumnIndex": col, "endColumnIndex": col + 1},
            "cell": {"userEnteredFormat": {
                "backgroundColor": {"red": 0.98, "green": 0.96, "blue": 0.90}}},
            "fields": "userEnteredFormat.backgroundColor"}})
        vreq.append({"setDataValidation": {
            "range": {"sheetId": vid, "startRowIndex": 1, "endRowIndex": 400,
                      "startColumnIndex": col, "endColumnIndex": col + 1},
            "rule": {
                "condition": {"type": "ONE_OF_LIST",
                              "values": [{"userEnteredValue": "yes"},
                                         {"userEnteredValue": "no"}]},
                # NOT strict: an empty cell must stay legal, because blank is
                # how Marcus says "you decide".
                "strict": False, "showCustomUi": True}}})

    ss.batch_update({"requests": vreq})
    print(f"Control tab formatted: frozen header, widths, yes/no dropdowns on "
          f"the two columns you own.")

    # ── the taste tab ──────────────────────────────────────────────────────
    try:
        tws = ss.worksheet(TASTE_TAB)
        print(f"Tab '{TASTE_TAB}' already exists — leaving its rows alone.")
    except Exception:
        tws = ss.add_worksheet(title=TASTE_TAB, rows=200,
                               cols=len(TASTE_HEADERS))
        print(f"Created tab '{TASTE_TAB}'.")
    tws.update(values=[TASTE_HEADERS], range_name="A1",
               value_input_option="RAW")
    tid = tws.id
    treq = [
        {"updateSheetProperties": {
            "properties": {"sheetId": tid,
                           "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount"}},
        {"repeatCell": {
            "range": {"sheetId": tid, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.93, "green": 0.93, "blue": 0.91}}},
            "fields": "userEnteredFormat(textFormat,backgroundColor)"}},
        {"repeatCell": {
            "range": {"sheetId": tid, "startRowIndex": 1,
                      "startColumnIndex": 1, "endColumnIndex": 2},
            "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}},
            "fields": "userEnteredFormat.wrapStrategy"}},
        {"setDataValidation": {
            "range": {"sheetId": tid, "startRowIndex": 1, "endRowIndex": 200,
                      "startColumnIndex": 2, "endColumnIndex": 3},
            "rule": {
                "condition": {"type": "ONE_OF_LIST",
                              "values": [{"userEnteredValue": v}
                                         for v in ("all", "reels",
                                                   "images", "educational")]},
                "strict": False, "showCustomUi": True}}},
    ]
    for i, w in enumerate([110, 520, 120, 140]):
        treq.append({"updateDimensionProperties": {
            "range": {"sheetId": tid, "dimension": "COLUMNS",
                      "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": w}, "fields": "pixelSize"}})
    ss.batch_update({"requests": treq})
    print("Taste Notes tab formatted.")

    print(f"\nDone.\n{reel_config.REEL_SHEET_URL}\n")
    print("TRIAL REELS tab: one row per published reel. Column Q (Notes) and")
    print("column W (Rating, 1-5) are yours; the lane READS them every tick and")
    print("tells the hook and caption writers. Views/Likes/Comments (N-P) and")
    print("Reach/Shares/Saves/Watch/Read (R-V) are filled in by the metrics")
    print("readback — but only when there is a real number, so anything you")
    print("typed by hand survives until a reading replaces it.")
    print()
    print("VIDEOS tab: one row per source video, added automatically the first")
    print("time the lane sees it, pre-filled from what it detected.")
    print("  'Text in video?'  no  -> the hook is burned onto the video")
    print("                    yes -> no overlay, the hook goes in the caption")
    print("  'Audio in video?' no  -> a licensed track is mixed in")
    print("                    yes -> your audio is left alone")
    print("  blank on either   -> the lane decides for itself")
    print("Your answers are never overwritten by a later run.")
    print()
    print("TASTE NOTES tab: directions not tied to one post ('captions")
    print("shorter', 'more hands in frame'). Date | Note | Applies to | Seen.")
    print("'Applies to' blank or 'all' = every lane. Seen is stamped by the")
    print("lane when it has read the row.")
    print("See what the writers are told: python3 reel_runner.py --feedback")
    print("To rebuild every row from state: python3 reel_sheet.py --rebuild\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
