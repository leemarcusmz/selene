# =============================================================================
# Selene Dreams — Image Generation Script v3.0
# google_services.py — Google Sheets, Drive, and Auth helpers
# =============================================================================

import io
import os
from datetime import datetime
from difflib import get_close_matches

import gspread
from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as OAuthCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

import config

# =============================================================================
# AUTH
# =============================================================================

SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]


def get_sheets_client():
    creds = Credentials.from_service_account_file(
        config.CREDENTIALS_FILE, scopes=SHEETS_SCOPES
    )
    return gspread.authorize(creds)


def get_drive_service():
    """OAuth-based Drive access tied to the user's personal account."""
    creds = None
    if os.path.exists(config.OAUTH_TOKEN_FILE):
        creds = OAuthCredentials.from_authorized_user_file(
            config.OAUTH_TOKEN_FILE, DRIVE_SCOPES
        )
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.OAUTH_CREDENTIALS_FILE, DRIVE_SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(config.OAUTH_TOKEN_FILE, "w") as token_file:
            token_file.write(creds.to_json())
    return build("drive", "v3", credentials=creds)


def get_google_services():
    return get_sheets_client(), get_drive_service()


# =============================================================================
# DRIVE — Folder helpers
# =============================================================================

MONTH_NUMBERS = {
    "January": "01", "February": "02", "March": "03", "April": "04",
    "May": "05", "June": "06", "July": "07", "August": "08",
    "September": "09", "October": "10", "November": "11", "December": "12",
}


def get_numbered_month(month):
    """'May' -> '05. May'. Two-digit zero-padded prefix."""
    n = MONTH_NUMBERS.get(month, "")
    return f"{n}. {month}" if n else month


def get_or_create_folder(drive_service, folder_name, parent_id):
    """Look up a folder by name under parent_id, creating it if missing."""
    query = (
        f"name='{folder_name}' and '{parent_id}' in parents and "
        f"mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    results = drive_service.files().list(
        q=query,
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = drive_service.files().create(
        body=metadata, fields="id", supportsAllDrives=True
    ).execute()
    return folder["id"]


def get_or_create_year_month_folder(drive_service, parent_id, year, month):
    """Returns the folder ID for {parent}/{year}/{05. May}."""
    year_id = get_or_create_folder(drive_service, str(year), parent_id)
    return get_or_create_folder(drive_service, get_numbered_month(month), year_id)


# (2026-07-22: get_unique_column_folder removed — output folders are now
# named "Row {n}", created only after a fully successful generation, and
# reused on re-runs. See generate.py.)


# =============================================================================
# DRIVE — File helpers
# =============================================================================

def _list_files_in_folder(drive_service, folder_id):
    query = f"'{folder_id}' in parents and trashed=false"
    files = []
    page_token = None
    while True:
        resp = drive_service.files().list(
            q=query,
            fields="nextPageToken, files(id, name, mimeType)",
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return files


def _build_source_filename(fabric, product_type, variant):
    def dashify(s):
        return s.strip().replace(" ", "-")
    return f"{dashify(fabric)}_{dashify(product_type)}_{dashify(variant)}"


def find_source_image(drive_service, fabric, product_type, variant):
    """
    Find the product source image in 01. Product Photos.

    Returns (file_id, file_name, error_dict_or_None).

    On miss, error_dict identifies which of fabric / product_type / variant
    is the likely typo (by checking which 2-of-3 partial match exists in the
    folder), and suggests a close match if possible.
    """
    files = _list_files_in_folder(
        drive_service, config.DRIVE_PRODUCT_PHOTOS_FOLDER_ID
    )
    file_names = [f["name"] for f in files]

    target_stem = _build_source_filename(fabric, product_type, variant)

    # Exact match (any extension)
    for f in files:
        name_no_ext = os.path.splitext(f["name"])[0]
        if name_no_ext.lower() == target_stem.lower():
            return f["id"], f["name"], None

    # Substring fallback (lets the longer descriptive names also match if you
    # ever want to keep them)
    for f in files:
        if target_stem.lower() in os.path.splitext(f["name"])[0].lower():
            return f["id"], f["name"], None

    # Diagnose which field is wrong by parsing the filenames in the folder.
    fabrics, types, variants = set(), set(), set()
    for fn in file_names:
        stem = os.path.splitext(fn)[0]
        parts = stem.split("_")
        if len(parts) >= 3:
            fabrics.add(parts[0].lower())
            types.add(parts[1].lower())
            variants.add(parts[2].lower())

    def _check(field_name, value, valid_set):
        v = value.strip().replace(" ", "-").lower()
        if v in valid_set:
            return None
        suggestion = get_close_matches(v, valid_set, n=1, cutoff=0.6)
        return {
            "field": field_name,
            "value": value,
            "suggestion": suggestion[0] if suggestion else None,
        }

    bad_fields = []
    for issue in (
        _check("Fabric", fabric, fabrics),
        _check("Product Type", product_type, types),
        _check("Variant", variant, variants),
    ):
        if issue:
            bad_fields.append(issue)

    if not bad_fields:
        # All three components individually exist, but the combination doesn't
        # — likely a missing source file for this specific variant.
        error = {
            "field": "combination",
            "value": target_stem,
            "suggestion": None,
            "message": (
                f"No file matching '{target_stem}.*' was found in "
                f"01. Product Photos, even though Fabric / Product Type / "
                f"Variant each appear in other filenames. Add the source "
                f"image with that exact name."
            ),
        }
    else:
        msgs = []
        for b in bad_fields:
            sug = f" — did you mean '{b['suggestion']}'?" if b["suggestion"] else ""
            msgs.append(f"{b['field']} '{b['value']}' not found{sug}")
        error = {
            "field": "+".join(b["field"] for b in bad_fields),
            "value": target_stem,
            "suggestion": None,
            "message": "; ".join(msgs),
        }
    return None, None, error


# (2026-07-22: find_reference_image removed — the Reference Image columns
# were dropped from the Generation Queue; generation uses the product source
# image + prompt only.)


def download_file_from_drive(drive_service, file_id):
    request = drive_service.files().get_media(
        fileId=file_id, supportsAllDrives=True
    )
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buffer.seek(0)
    return buffer.read()


def upload_file_to_drive(drive_service, file_bytes, filename, folder_id,
                         max_retries=3):
    """
    Upload a PNG to Drive with resumable transfer + retry on broken pipe.

    The generation pipeline can sit idle for 60–120s while polling Replicate,
    which lets the Drive client's HTTP keepalive go stale. On the first
    upload after a long wait we sometimes hit "Broken pipe" (Errno 32) or
    a connection reset. Resumable uploads recover from partial failures,
    and the outer retry loop handles complete socket resets.
    """
    import time as _time
    from socket import error as SocketError

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            metadata = {"name": filename, "parents": [folder_id]}
            media = MediaIoBaseUpload(
                io.BytesIO(file_bytes),
                mimetype="image/png",
                resumable=True,
                chunksize=1024 * 1024,  # 1 MB chunks
            )
            request = drive_service.files().create(
                body=metadata,
                media_body=media,
                fields="id, webViewLink",
                supportsAllDrives=True,
            )
            response = None
            while response is None:
                _status, response = request.next_chunk(num_retries=3)
            return response.get("webViewLink", "")
        except (BrokenPipeError, ConnectionResetError, SocketError,
                OSError) as e:
            last_error = e
            print(f"    Upload attempt {attempt} failed: {e}. Retrying...")
            _time.sleep(2 * attempt)
        except Exception as e:
            # Non-network errors — don't retry, just raise
            raise
    raise RuntimeError(
        f"Upload failed after {max_retries} attempts. Last error: {last_error}"
    )


# =============================================================================
# SHEETS — Generation Status tab helpers (control panel, added 2026-07-22)
# =============================================================================

def get_gs_sheet(queue_sheet):
    """
    Return the 'Generation Status' worksheet from the same spreadsheet as the
    queue worksheet, or None if the tab doesn't exist (all GS writes are then
    skipped gracefully so the pipeline still works).
    """
    try:
        return queue_sheet.spreadsheet.worksheet(config.GS_SHEET_NAME)
    except Exception as e:
        print(f"    WARNING: Generation Status tab unavailable ({e}); "
              f"skipping control-panel writes.")
        return None


def find_gs_row(gs_sheet, row_number):
    """
    Locate the Generation Status row for a given queue # by scanning col B.
    Fallback: positional mapping (# + GS_FIRST_DATA_ROW - 1).
    """
    try:
        col_b = gs_sheet.col_values(config.GS_COL_NUMBER)
        for i, v in enumerate(col_b, start=1):
            if i < config.GS_FIRST_DATA_ROW:
                continue
            if str(v).strip() == str(row_number):
                return i
    except Exception:
        pass
    return row_number + config.GS_FIRST_DATA_ROW - 1


def gs_write(gs_sheet, gs_row, col_one_based, value):
    gs_sheet.update_cell(gs_row, col_one_based, value)


def gs_get_gen_status(queue_sheet, row_number):
    """Read the generation Status (col D) for a queue # from the GS tab.
    Returns None if the tab is missing (caller falls back to queue col Q)."""
    gs = get_gs_sheet(queue_sheet)
    if gs is None:
        return None
    r = find_gs_row(gs, row_number)
    try:
        return str(gs.cell(r, config.GS_COL_GEN_STATUS).value or "").strip()
    except Exception:
        return None


def gs_set_gen_status(queue_sheet, row_number, status):
    gs = get_gs_sheet(queue_sheet)
    if gs is None:
        return
    r = find_gs_row(gs, row_number)
    gs_write(gs, r, config.GS_COL_GEN_STATUS, status)


def gs_append_remark(gs, gs_row, message):
    """Append to System Remark(s) col M without clobbering earlier notes."""
    try:
        existing = str(gs.cell(gs_row, config.GS_COL_SYS_REMARK).value or "").strip()
    except Exception:
        existing = ""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    new = f"[{stamp}] {message}"
    gs_write(gs, gs_row, config.GS_COL_SYS_REMARK,
             f"{existing} | {new}" if existing else new)


def gs_mark_generation_done(queue_sheet, row_number, note=None):
    """D=Done, E=Completion Date, F=Completion Time; caption G unlocks.

    v14 (2026-08-21): G now goes straight to 'Ready' instead of stopping at
    'Not Started'. 'Not Started' existed to wait for a human flip, and that
    gate is gone — judgement moved to the review screen, which looks at the
    finished post rather than the prompt.

    Setting the cell does NOT start anything on its own: trigger.gs's
    handleEdit is an on-edit trigger and Google's on-edit triggers ignore
    writes made through the Sheets API. generate.py calls
    chain.fire_caption() immediately after this to actually start the run.
    """
    gs = get_gs_sheet(queue_sheet)
    if gs is None:
        return
    r = find_gs_row(gs, row_number)
    now = datetime.now()
    gs_write(gs, r, config.GS_COL_GEN_STATUS, config.STATUS_DONE)
    gs_write(gs, r, config.GS_COL_GEN_DATE, now.strftime("%Y-%m-%d"))
    gs_write(gs, r, config.GS_COL_GEN_TIME, now.strftime("%H:%M"))
    try:
        cap = str(gs.cell(r, config.GS_COL_CAP_STATUS).value or "").strip()
    except Exception:
        cap = ""
    if cap in ("", config.CAP_STATUS_NOT_AVAILABLE, config.CAP_STATUS_NOT_STARTED):
        gs_write(gs, r, config.GS_COL_CAP_STATUS, config.CAP_STATUS_READY)
    if note:
        gs_append_remark(gs, r, note)


def gs_mark_generation_error(queue_sheet, row_number, message):
    """D=ERROR and the error message into System Remark(s) col M."""
    gs = get_gs_sheet(queue_sheet)
    if gs is None:
        return
    r = find_gs_row(gs, row_number)
    gs_write(gs, r, config.GS_COL_GEN_STATUS, config.STATUS_ERROR)
    gs_append_remark(gs, r, f"IMAGE: {message}")


def _queue_row_number(queue_row_values, row_index):
    """Best-effort # for a queue row (col A formula, fallback row-1)."""
    try:
        return int(str(queue_row_values[config.COL_NUMBER]).strip())
    except (ValueError, IndexError):
        return row_index - 1


# =============================================================================
# SHEETS — Row helpers
# =============================================================================

def _pad(row, n=config.TOTAL_COLS):
    while len(row) < n:
        row.append("")
    return row


def get_ready_rows(sheet, filter_current_month=True):
    """
    Rows whose control status is 'Ready'.

    2026-07-22: the control status lives ONLY in the Generation Status tab
    (col D, keyed by #) — the queue's old Status column was removed. If the
    tab can't be read there is nothing to process.
    """
    all_rows = sheet.get_all_values()

    gs = get_gs_sheet(sheet)
    if gs is None:
        print("    Generation Status tab unavailable — no Ready rows.")
        return []
    try:
        gs_values = gs.get_all_values()
    except Exception as e:
        print(f"    WARNING: could not read Generation Status tab ({e}).")
        return []
    gs_ready_numbers = set()
    for gi, gr in enumerate(gs_values, start=1):
        if gi < config.GS_FIRST_DATA_ROW:
            continue
        num = str(gr[config.GS_COL_NUMBER - 1]).strip() \
            if len(gr) >= config.GS_COL_NUMBER else ""
        st = str(gr[config.GS_COL_GEN_STATUS - 1]).strip() \
            if len(gr) >= config.GS_COL_GEN_STATUS else ""
        if num and st == config.STATUS_READY:
            gs_ready_numbers.add(num)

    ready = []
    skipped = []
    current_year = str(datetime.now().year)
    current_month = datetime.now().strftime("%B")
    for i, row in enumerate(all_rows):
        if i == 0:
            continue
        row = _pad(list(row))
        num = str(row[config.COL_NUMBER]).strip()
        if num not in gs_ready_numbers:
            continue
        if filter_current_month:
            if (
                row[config.COL_YEAR].strip() == current_year
                and row[config.COL_MONTH].strip().lower() == current_month.lower()
            ):
                ready.append((i + 1, row))
            else:
                skipped.append((i + 1, row[config.COL_YEAR], row[config.COL_MONTH]))
        else:
            ready.append((i + 1, row))
    if skipped:
        print(
            f"\nWARNING: {len(skipped)} row(s) skipped (Year/Month != current "
            f"{current_month} {current_year})"
        )
    return ready


def write_cell(sheet, row_index, col_index_zero_based, value):
    sheet.update_cell(row_index, col_index_zero_based + 1, value)


def update_sheet_success(sheet, row_index, credits_used,
                         output_folder, image_urls, carousel_id):
    """Write result data to the queue row and mark the Generation Status
    control row Done with completion date/time (E/F). The queue's old Status
    column was removed 2026-07-22 — the GS tab is the only status surface."""
    write_cell(sheet, row_index, config.COL_CREDITS, credits_used)
    write_cell(sheet, row_index, config.COL_OUTPUT_FOLDER, output_folder)
    write_cell(sheet, row_index, config.COL_IMAGE_URLS, ", ".join(image_urls))
    write_cell(sheet, row_index, config.COL_CAROUSEL_ID, carousel_id)
    gs_mark_generation_done(sheet, row_index - 1)


def update_sheet_error(sheet, row_index, message):
    """ERROR on the Generation Status row (col D) with the message appended
    to System Remark(s) col M; the queue Notes col keeps a backup copy."""
    write_cell(sheet, row_index, config.COL_NOTES, f"ERROR: {message}")
    gs_mark_generation_error(sheet, row_index - 1, message)
