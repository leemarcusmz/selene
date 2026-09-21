# =============================================================================
# Selene Dreams — Pending Pick Rerun v1.3 (2026-08-31)
# rerun_pending_pick.py — finish a weekly pick whose /select call never landed
# =============================================================================
#
# WHY THIS EXISTS
#   When a teammate submits on the picker, Apps Script POSTs /select to this
#   Mac through the ngrok tunnel. The submission itself is recorded either
#   way — LockService locks the week and the row is appended — but if that
#   POST fails the row is left at:
#
#       "PENDING — Mac offline; ask Claude to run the pending pick"
#
#   which names the wrong cause more often than the right one: the Mac is
#   usually awake and Flask usually healthy. What died is the TUNNEL between
#   them, and from Apps Script's side the two are indistinguishable.
#
# THE BUG THIS REPLACES (found 2026-08-31)
#   The documented recovery was "the payload JSON is in the row's Details
#   column — run prompt_runner.py --json <that>". It cannot work. picker.gs
#   writes `JSON.stringify(payload.picks)` into Details — the picks ARRAY
#   alone. run_selection() wants the whole envelope, {week, picker, picks}.
#   Feeding it the Details cell hands a bare list to code that calls .get()
#   on it. The week and picker live in columns 1 and 2 of the same row, so
#   the payload is reconstructable — this script does that, and skips the
#   clipboard, which is its own failure mode (an empty pbpaste produces
#   "Expecting value: line 1 column 1", which reads like malformed JSON
#   rather than no JSON).
#
# USAGE
#   python3 rerun_pending_pick.py              # newest pending week
#   python3 rerun_pending_pick.py --list       # show them, run nothing
#   python3 rerun_pending_pick.py --week 2026-08-31
#   python3 rerun_pending_pick.py --week 2026-08-31 --only 5,7 --include-done
#       ^ retry just the posts that failed, on a row already marked done.
#         WITHOUT --only, rerunning a completed row re-adds EVERY post as a
#         NEW queue row — nothing dedupes them. Always pair --include-done
#         with --only.
#
# NOTE ON AGE
#   picks carry Instagram CDN slide URLs, which die within days. Rerunning a
#   pick from weeks ago will fail its downloads — that is the CDN, not this
#   script. Rerun promptly.
#
# CHANGELOG
#   1.3  2026-08-31  DUPLICATE GUARD. --only stopped a full rerun from
#                    re-adding finished posts, but nothing stopped the SAME
#                    --only command being run twice: on 2026-08-31 posts 5
#                    and 7 were added again as rows #28/#29, four hours after
#                    #26/#27, and the auto-chain queued both for generation
#                    against a 15-image weekly cap. Every post whose postUrl
#                    already has a queue row in pipeline-state is now skipped
#                    unless --force says otherwise.
#   1.2  2026-08-31  --only and --include-done, so the posts that failed a
#                    partial run can be retried without duplicating the ones
#                    that succeeded.
#   1.1  2026-08-31  Use get_sheets_client(), not get_google_services(): the
#                    latter eagerly builds the OAuth Drive client, and an
#                    expired Drive token was failing this script over a
#                    service neither it nor prompt_runner actually uses.
#   1.0  2026-08-31  First build. Replaces the broken --json/Details recovery.
# =============================================================================

import argparse
import json
import sys

import config
import pipeline_state
import prompt_runner
from google_services import get_sheets_client

PICKS_SHEET = prompt_runner.PICKS_SHEET
COL_WEEK, COL_PICKER, COL_STATUS, COL_DETAILS = 1, 2, 6, 7
SHEETS_CELL_LIMIT = 50000


def pending_rows(sheet, include_done=False):
    """Rows waiting on a prompt run, newest week first.

    include_done also returns rows that already completed — needed to retry
    the failed posts of a PARTIAL run, whose status is no longer PENDING.
    """
    out = []
    for i, row in enumerate(sheet.get_all_values(), start=1):
        if i == 1 or not any(row):
            continue
        cell = lambda c: row[c - 1] if len(row) >= c else ""
        if not include_done and not str(
                cell(COL_STATUS)).strip().upper().startswith("PENDING"):
            continue
        out.append({"row": i, "week": cell(COL_WEEK).strip(),
                    "picker": cell(COL_PICKER).strip(),
                    "details": cell(COL_DETAILS),
                    "status": cell(COL_STATUS)})
    out.sort(key=lambda r: r["week"], reverse=True)
    return out


def build_payload(rec):
    raw = rec["details"] or ""
    if not raw.strip():
        raise ValueError(f"row {rec['row']}: Details is empty — nothing to rerun")
    if len(raw) >= SHEETS_CELL_LIMIT:
        raise ValueError(
            f"row {rec['row']}: Details is {len(raw)} chars and may be truncated "
            f"at the {SHEETS_CELL_LIMIT}-char cell cap — do not trust it")
    try:
        picks = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"row {rec['row']}: Details is not valid JSON ({e})")
    if not isinstance(picks, list) or not picks:
        raise ValueError(
            f"row {rec['row']}: Details should be a non-empty LIST of picks, "
            f"got {type(picks).__name__}")
    # The envelope picker.gs never wrote to the sheet.
    return {"week": rec["week"], "picker": rec["picker"], "picks": picks}


def main():
    ap = argparse.ArgumentParser(description="Rerun a pending weekly pick")
    ap.add_argument("--week", help="Specific week (default: newest pending)")
    ap.add_argument("--list", action="store_true",
                    help="List pending picks and exit")
    ap.add_argument("--only",
                    help="Comma-separated post numbers to run (e.g. 5,7). "
                         "Everything else in the row is skipped.")
    ap.add_argument("--force", action="store_true",
                    help="Re-add posts that already have a queue row. Almost "
                         "never right — it duplicates the row AND re-fires "
                         "image generation against the weekly cap.")
    ap.add_argument("--include-done", action="store_true",
                    help="Also consider rows that already completed. Use ONLY "
                         "with --only: a full rerun duplicates queue rows.")
    args = ap.parse_args()

    sheets_client = get_sheets_client()   # Sheets only — see v1.1 note
    sheet = sheets_client.open_by_key(config.GOOGLE_SHEET_ID).worksheet(PICKS_SHEET)

    rows = pending_rows(sheet, include_done=args.include_done)
    if not rows:
        print("No pending picks — nothing to rerun."
              if not args.include_done else "No matching rows.")
        return 0

    if args.list:
        for r in rows:
            try:
                n = len(json.loads(r["details"] or "[]"))
            except Exception:
                n = "?"
            print(f"  row {r['row']}  week {r['week']}  picked by {r['picker']}  "
                  f"{n} post(s)")
        return 0

    if args.week:
        rows = [r for r in rows if r["week"] == args.week]
        if not rows:
            print(f"No pending pick for week {args.week}.")
            return 1

    rec = rows[0]
    payload = build_payload(rec)

    if args.only:
        want = {t.strip() for t in args.only.split(",") if t.strip()}
        payload["picks"] = [p for p in payload["picks"]
                            if str(p.get("n")) in want]
        if not payload["picks"]:
            print(f"None of posts {sorted(want)} are in week {rec['week']}.")
            return 1
    elif args.include_done:
        print("REFUSING: --include-done without --only would re-add every "
              "post in this row as a new queue row. Name the posts to retry "
              "with --only.")
        return 1

    # Already-generated posts: pipeline_state records the referenceUrl
    # (= postUrl) of every queue row prompt_runner has written.
    if not args.force:
        done = set()
        try:
            st = pipeline_state.load_state()
            for row in (st.get("rows") or {}).values():
                u = ((row.get("prompts") or {}).get("referenceUrl") or "").strip()
                if u:
                    done.add(u)
        except Exception as e:
            print(f"NOTE: could not read pipeline state ({e}) — "
                  f"duplicate check skipped.")
        dupes = [p for p in payload["picks"] if p.get("postUrl") in done]
        if dupes:
            for p in dupes:
                print(f"  SKIP post #{p.get('n')} — already has a queue row "
                      f"(re-adding would duplicate it and re-fire generation)")
            payload["picks"] = [p for p in payload["picks"] if p not in dupes]
        if not payload["picks"]:
            print("Every requested post already has a queue row. "
                  "Nothing to do. (--force overrides.)")
            return 0

    print(f"Rerunning week {rec['week']} — picked by {rec['picker']}, "
          f"{len(payload['picks'])} post(s)"
          f"{' (filtered to ' + args.only + ')' if args.only else ''}.")
    ok, msg = prompt_runner.run_selection(payload)
    print(("SUCCESS: " if ok else "FAILED: ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
