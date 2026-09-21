# =============================================================================
# setup_library_v2.py — one-off: Image Library v2 columns + the Sources tab
# VERSION 1.0 — 2026-09-10
# CHANGELOG
#   1.0  2026-09-10  First release. Marcus's matching design (2026-09-10): every
#                    image carries a sentence description, structured fields, and
#                    two facts only he can supply - is it OUR product, and which.
#                    Those two are inherited from a Sources tab he fills once per
#                    Drive folder, so a shoot of 40 frames is labelled in one row.
#                    Idempotent: re-running adds nothing that already exists.
# =============================================================================
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config_edu as C
import sheets_edu as S

LIB_HEADERS_V2 = ["Description", "Setting", "Action", "People", "Light",
                  "Ours", "Product", "Source Folder", "Non-Brand", "Brief"]
# K..T. A-J are the v1 columns and stay exactly as they are.

SOURCES_HEADERS = ["Folder (Drive path under the Selene root)", "Ours (Yes/No)",
                   "Product(s) in these frames", "Shoot Date", "Notes",
                   "Indexed (auto)"]

SOURCES_NOTE = ("One row per Drive folder of images. Ours = Yes means these frames show "
                "Selene's actual product; Product names what is in them (e.g. French Linen "
                "Moss, Organic Percale White). The tagger inherits both onto every image "
                "under that folder. Add a folder here and the next tick indexes it.")


def run(apply=True):
    ss = S.edu_sheet()
    lib = S.tab(C.TAB_LIBRARY)
    vals = lib.get_all_values()
    header = vals[0] if vals else []
    missing = [h for h in LIB_HEADERS_V2 if h not in header]
    print(f"Image Library: {len(vals)-1} rows, header has {len(header)} cols, missing {missing}")
    if missing and apply:
        start_col = len(header) + 1
        need = start_col + len(missing) - 1
        if lib.col_count < need:
            lib.add_cols(need - lib.col_count)
        from gspread.utils import rowcol_to_a1
        a1 = rowcol_to_a1(1, start_col)
        lib.update(values=[missing], range_name=f"{a1}:{rowcol_to_a1(1, need)}")
        print(f"  added columns {a1}..{rowcol_to_a1(1, need)}")

    titles = [w.title for w in ss.worksheets()]
    if C.TAB_SOURCES not in titles:
        print(f"Sources tab: creating '{C.TAB_SOURCES}'")
        if apply:
            ws = ss.add_worksheet(title=C.TAB_SOURCES, rows=100, cols=8)
            # existing folders, pre-filled as the v3.0 lane's AI generations
            seen, rows = set(), []
            for r in vals[1:]:
                src = (r[1] if len(r) > 1 else "").split(":", 1)[-1].strip()
                folder = "/".join(src.split("/")[:-1]) or src
                if folder and folder not in seen:
                    seen.add(folder)
                    rows.append([f"{C.GENERATED_IMAGES_FOLDER_NAME}/{folder}", "No",
                                 "", "", "AI generations from the image lane (v3.0)", "Yes"])
            ws.update(values=[[SOURCES_NOTE], SOURCES_HEADERS] + rows, range_name="A1")
            ws.format("A1", {"textFormat": {"italic": True}})
            ws.format("A2:F2", {"textFormat": {"bold": True}})
            print(f"  pre-filled {len(rows)} existing folders (Ours = No)")
    else:
        print(f"Sources tab: exists")
    return "ok"


if __name__ == "__main__":
    run(apply="--dry-run" not in sys.argv)
