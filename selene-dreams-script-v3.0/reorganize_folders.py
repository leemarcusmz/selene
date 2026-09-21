# =============================================================================
# Selene Dreams — One-off Drive folder reorganization (2026-07-22)
# reorganize_folders.py
# =============================================================================
#
# Fixes the "03. Generated Images" month folders so every folder matches its
# actual Generation Queue row:
#
#   1. For each queue row that has an Output Folder recorded, rename that
#      folder to "Row {#}" and update the sheet's Output Folder cell.
#   2. Any other "Column ..." folders in the month (leftovers from failed or
#      re-run generations) are MOVED into an "_archive" subfolder — nothing
#      is deleted, so you can review and empty _archive yourself.
#
# Run it once from the v3.0 folder:
#   python3 reorganize_folders.py            # dry run — shows the plan only
#   python3 reorganize_folders.py --apply    # actually do it
# =============================================================================

import argparse
import re
from datetime import datetime

import config
from google_services import (
    get_google_services,
    get_or_create_folder,
    _list_files_in_folder,
)


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def rename_folder(drive, folder_id, new_name):
    drive.files().update(
        fileId=folder_id, body={"name": new_name}, supportsAllDrives=True
    ).execute()


def move_folder(drive, folder_id, old_parent, new_parent):
    drive.files().update(
        fileId=folder_id, addParents=new_parent, removeParents=old_parent,
        supportsAllDrives=True,
    ).execute()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Apply changes (default is a dry run)")
    args = parser.parse_args()
    dry = not args.apply

    sheets, drive = get_google_services()
    queue = sheets.open_by_key(config.GOOGLE_SHEET_ID).worksheet(
        config.GOOGLE_SHEET_NAME)
    rows = queue.get_all_values()

    # Map: (year, numbered_month) -> { recorded_folder_name: (queue_row, #) }
    referenced = {}
    for i, row in enumerate(rows):
        if i == 0:
            continue
        while len(row) < config.TOTAL_COLS:
            row.append("")
        out = row[config.COL_OUTPUT_FOLDER].strip()
        if not out:
            continue
        m = re.match(r"^(\d{4})/(\d{2}\. \w+)/(.+)$", out)
        if not m:
            log(f"  WARNING: row {i+1} Output Folder not parseable: '{out}'")
            continue
        year, nmonth, folder_name = m.group(1), m.group(2), m.group(3)
        referenced.setdefault((year, nmonth), {})[folder_name] = (i + 1, i)

    if not referenced:
        log("No Output Folder values found — nothing to do.")
        return

    for (year, nmonth), mapping in referenced.items():
        log(f"Month: {year}/{nmonth}")
        # Resolve the month folder
        year_id = get_or_create_folder(
            drive, year, config.DRIVE_GENERATED_IMAGES_FOLDER_ID)
        month_id = get_or_create_folder(drive, nmonth, year_id)
        entries = [
            f for f in _list_files_in_folder(drive, month_id)
            if f["mimeType"] == "application/vnd.google-apps.folder"
        ]
        by_name = {f["name"]: f["id"] for f in entries}
        claimed = set()

        # Pass 1 — rename referenced folders to "Row {#}"
        for folder_name, (queue_row, number) in sorted(
                mapping.items(), key=lambda kv: kv[1][1]):
            target = f"Row {number}"
            fid = by_name.get(folder_name)
            if fid is None:
                log(f"  MISSING: '{folder_name}' (row #{number}) not found "
                    f"in Drive — sheet cell left as is.")
                continue
            claimed.add(fid)
            if folder_name == target:
                log(f"  OK: '{folder_name}' already correct.")
                continue
            if target in by_name and by_name[target] != fid:
                log(f"  CONFLICT: can't rename '{folder_name}' → '{target}' "
                    f"(a different '{target}' already exists). Skipped.")
                continue
            log(f"  RENAME: '{folder_name}' → '{target}'  (#{number})")
            if not dry:
                rename_folder(drive, fid, target)
                queue.update_cell(
                    queue_row, config.COL_OUTPUT_FOLDER + 1,
                    f"{year}/{nmonth}/{target}")

        # Pass 2 — archive unreferenced Column/Row folders
        strays = [f for f in entries
                  if f["id"] not in claimed
                  and re.match(r"^(Column|Row) \d+", f["name"])
                  and f["name"] != "_archive"]
        if strays:
            archive_id = None
            if not dry:
                archive_id = get_or_create_folder(drive, "_archive", month_id)
            for f in strays:
                log(f"  ARCHIVE: '{f['name']}' → _archive/ (unreferenced)")
                if not dry:
                    move_folder(drive, f["id"], month_id, archive_id)

    if dry:
        print("\nDry run only — nothing was changed. "
              "Re-run with --apply to execute the plan above.")
    else:
        print("\nDone. Review the _archive folder(s) and delete them "
              "yourself when you're satisfied.")


if __name__ == "__main__":
    main()
