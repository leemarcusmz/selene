#!/usr/bin/env python3
"""
reschedule_missed.py — v1.0 (2026-09-04)
One-off: restagger the 4 posts that missed their slots while the server
was down (2026-09-01 03:21 -> 2026-09-04). Moves K to daily 21:00-NY
slots and appends a SCHEDULE remark to M. J stays 'Scheduled'.
Run BEFORE restarting "Start Selene AI", or all 4 fire at once.

Changelog:
- v1.0 (2026-09-04): initial one-off. #22->09-04, #25->09-05,
  #26->09-06, #24->09-07.
"""
import datetime
import google_services as g
import config

NEW_K = {"22": "2026-09-04", "25": "2026-09-05",
         "26": "2026-09-06", "24": "2026-09-07"}


def main():
    client = g.get_sheets_client()
    sh = client.open_by_key(config.GOOGLE_SHEET_ID)
    ws = sh.worksheet(config.GS_SHEET_NAME)
    rows = ws.get_all_values()
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    for i, r in enumerate(rows):
        n = r[1] if len(r) > 1 else ""
        if n not in NEW_K:
            continue
        row = i + 1
        j = r[9] if len(r) > 9 else ""
        if j != "Scheduled":
            print(f"#{n}: SKIP (J={j!r}, expected 'Scheduled')")
            continue
        old_k = r[10] if len(r) > 10 else ""
        ws.update_cell(row, 11, NEW_K[n])
        m = r[12] if len(r) > 12 else ""
        note = (f"[{ts}] SCHEDULE: missed slot (server down since "
                f"2026-09-01) — moved {old_k} -> {NEW_K[n]}")
        ws.update_cell(row, 13, (m + " | " + note) if m else note)
        print(f"#{n} (row {row}): K {old_k} -> {NEW_K[n]}")
    print("Done. Now restart 'Start Selene AI'.")

if __name__ == "__main__":
    main()
