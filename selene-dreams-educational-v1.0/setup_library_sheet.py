# =============================================================================
# setup_library_sheet.py — one-off: move Image Library + Sources to their own
#                          spreadsheet, "Selene Dreams — Image Library"
# VERSION 1.0 — 2026-09-10
# CHANGELOG
#   1.0  2026-09-10  First release. Marcus (2026-09-10): the library is brand
#                    content, not educational-lane content, and other flows will
#                    read it - so it gets its own spreadsheet beside the others.
#                    Created through the OAuth Drive token so Marcus OWNS it (a
#                    service account has no storage quota and would own it
#                    invisibly), then shared with the service account as editor.
#                    Tabs are copied with formatting, the originals renamed
#                    "zz_moved ..." and hidden, never deleted by this script.
#                    Prints the new sheet id for config_edu.IMAGE_LIBRARY_SHEET_ID.
# =============================================================================
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config_edu as C
import sheets_edu as S
import library_edu as L

NEW_NAME = "Selene Dreams — Image Library"


def run():
    d = L.drive()
    parent = d.files().get(fileId=C.EDU_QUEUE_SHEET_ID, fields="parents").execute()["parents"][0]
    # already there?
    res = d.files().list(q=f"name = '{NEW_NAME}' and '{parent}' in parents and trashed = false",
                         fields="files(id,name)").execute()
    if res.get("files"):
        new_id = res["files"][0]["id"]
        print(f"exists: {new_id}")
    else:
        new_id = d.files().create(body={"name": NEW_NAME, "parents": [parent],
                                        "mimeType": "application/vnd.google-apps.spreadsheet"},
                                  fields="id").execute()["id"]
        print(f"created: {new_id}")
    sa = json.load(open(C.CREDENTIALS_PATH))["client_email"]
    d.permissions().create(fileId=new_id, sendNotificationEmail=False,
                           body={"type": "user", "role": "writer", "emailAddress": sa}).execute()
    print(f"shared with {sa}")

    src = S.edu_sheet()._ss
    dst = S.gc().open_by_key(new_id)
    have = {w.title for w in dst.worksheets()}
    for name in (C.TAB_LIBRARY, C.TAB_SOURCES):
        if name in have:
            print(f"{name}: already in the new sheet"); continue
        ws = src.worksheet(name)
        copied = ws.copy_to(new_id)               # keeps formatting + column widths
        dst = S.gc().open_by_key(new_id)
        cw = next(w for w in dst.worksheets() if w.id == copied["sheetId"])
        cw.update_title(name)
        print(f"{name}: copied ({cw.row_count} rows)")
        ws.update_title(f"zz_moved {name}")
        ws.hide()
    # drop the default empty tab
    dst = S.gc().open_by_key(new_id)
    for w in dst.worksheets():
        if w.title in ("Sheet1", "工作表1") and len(dst.worksheets()) > 1:
            dst.del_worksheet(w)
    # order: Image Library first
    lib = dst.worksheet(C.TAB_LIBRARY); lib.update_index(0)
    print(f"\nIMAGE_LIBRARY_SHEET_ID = \"{new_id}\"")
    return new_id


if __name__ == "__main__":
    run()
