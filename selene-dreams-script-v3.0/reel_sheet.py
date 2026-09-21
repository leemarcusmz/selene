"""
reel_sheet.py — mirror every published trial reel into a Google Sheet
=============================================================================
VERSION 2.5 — 2026-09-16

TWO TABS, TWO DIFFERENT JOBS
    "Trial Reels"  — the MIRROR. One row per published reel: hook, caption,
                     video, pattern, mode. Written only, never read back.
    "Videos"       — the CONTROL TAB (v2.0). One row per source video, where
                     Marcus declares whether it already has on-screen text and
                     whether it already has audio. Those two answers decide
                     overlay and music per video.

THE CONTROL TAB IS AN OPTIONAL INPUT, NOT A DEPENDENCY
    This lane was deliberately built with no sheet so it could keep publishing
    through a Drive or Sheets outage — the failure that has twice silently
    stopped the carousel lane. Making the sheet an INPUT threatens that, so:

      the lane AUTO-DETECTS both signals on its own (the vision pass reports
      on-screen text; video_host.is_effectively_silent reports real audio),
      writes them into the tab as defaults, and uses Marcus's override ONLY
      when the sheet is readable and he has actually set one.

    Sheet unreachable, row missing, cell blank -> auto-detection decides and the
    reel publishes anyway. He gets control; the lane keeps its independence.

    _state/reels.json remains the source of truth for what has been POSTED,
    what is on cooldown, and which variant is next. None of that is ever read
    from the sheet.

FAIL-OPEN, ALWAYS
    Every function here swallows its own errors and returns False. A sheet that
    is unreachable, unshared, renamed or rate-limited must never stop a reel
    from publishing or crash the runner. The failure is logged and the run
    continues, exactly like product tagging in publish_runner v1.2.

GSPREAD ARGUMENT ORDER
    Every update() call here uses NAMED arguments (values=, range_name=).
    gspread 6 swapped the positional order to update(values, range_name) and
    keeps a deprecation shim for the old order. caption_runner.py:364 still
    relies on that shim — it works today and emits a DeprecationWarning, but it
    will break when the shim is removed. Named arguments are correct under both
    5.x and 6.x, so new code uses them and needs no version pin.

COLUMN ORDER IS DELIBERATELY ODD (v2.1)
    Metrics land in N/O/P and then jump to R/S/T/U/V, leaving "Notes" alone in
    Q. Tidier would be to group all the numbers together — but that would move
    the Notes column, and rebuild() restores manual cells BY POSITION. Moving Q
    would silently shift every note Marcus has already typed one column left.
    An ugly header row is cheaper than losing his writing.

CHANGELOG
    2.5  2026-09-16  RATING column (W) and the Taste Notes tab. Both are
                     Marcus's; the lane reads them (reel_feedback.py) and
                     writes only the Seen stamp on the taste tab. W is
                     appended at the END so no existing cell moves, and
                     rebuild() already preserves everything right of M by
                     position. _open_tab knows the taste tab's headers.
    2.4  2026-09-11  A row can now be created WITHOUT a guess in it. Rows used
                     to appear only when a video was published, so with a post
                     every 40 hours the twelve New Zealand clips would have
                     taken three weeks to become settable — the control tab was
                     unreachable for exactly the videos that needed it. The
                     runner's --index fills it in advance, and detection values
                     it does not have (text needs the vision pass) are written
                     BLANK rather than as "no". A blank means "nobody has
                     decided"; writing "no" would look like an answer.
    2.3  2026-09-11  FRAMING column on the control tab. Non-vertical footage is
                     composed onto a 9:16 canvas at publish time; this is where
                     Marcus says crop or fit per video. Blank = the lane
                     decides (fit, the treatment that cannot lose anything).
                     Appended at the END of the Videos tab so no existing cell
                     moves.
    2.2  2026-09-11  Probe readings are labelled as such in column V ("probe
                     @45h") rather than borrowing a window's name, and a real
                     window always outranks a probe when both exist.
    2.1  2026-09-10  METRICS. N/O/P stop being manual: reel_metrics writes them
                     after each read window, along with reach, shares, saves,
                     watch time and a stamp saying which window the row shows.
                     A cell is only ever written when there is a real number
                     for it, so anything typed by hand survives until a reading
                     replaces it.
    2.0  2026-09-09  The control tab.
    1.0  2026-09-09  First build.
=============================================================================
"""

import reel_config

HEADERS = [
    "#",                 # A  sequential, assigned by the sheet
    "Published",         # B  local time
    "Video",             # C  the source file in 00. Drop Here
    "Variant",           # D  which hook variant of that video
    "Hook",              # E  <- what Marcus asked to be able to see
    "Hook pattern",      # F  H2 / H3 / H5 and its name
    "Evidence",          # G  STRONG / MEDIUM / WEAK — how much to trust it
    "Mode",              # H  caption or overlay
    "Overlay",           # I  treatment + contrast, blank in caption mode
    "Caption style",     # J  One Line / Two Beat / Meet the Product
    "Caption",           # K  <- the full caption, as published
    "Hashtags",          # L  split out so the caption column stays readable
    "Permalink",         # M
    "Views",             # N  written by reel_metrics
    "Likes",             # O  written by reel_metrics
    "Comments",          # P  written by reel_metrics
    "Notes",             # Q  YOURS — never written, never moved (see above)
    "Reach",             # R  written by reel_metrics
    "Shares",            # S  written by reel_metrics
    "Saves",             # T  written by reel_metrics
    "Avg watch (s)",     # U  written by reel_metrics
    "Metrics read",      # V  which window these numbers are, and when
    "Rating",            # W  YOURS — 1 to 5, read by reel_feedback
]
RATING_COL = "W"

# metric name in reel_metrics -> column letter
METRIC_COLS = {
    "views": "N",
    "likes": "O",
    "comments": "P",
    "reach": "R",
    "shares": "S",
    "saved": "T",
}
PERMALINK_COL = 12          # zero-based index of M in a row list

# Columns build_row() produces, i.e. A-M. Everything from N rightwards is
# written separately, by reel_metrics, keyed on the permalink in M.
WRITTEN_COLS = 13

# ── the taste tab ───────────────────────────────────────────────────────────
# Free-text directions not tied to one post. Read by reel_feedback; the lane
# writes only column D (Seen).
TASTE_TAB = reel_config.TASTE_TAB
TASTE_HEADERS = ["Date", "Note", "Applies to", "Seen"]

# ── the control tab ─────────────────────────────────────────────────────────
VIDEO_TAB = "Videos"

VIDEO_HEADERS = [
    "Video",             # A  the Drive filename
    "Product",           # B  from the filename, or type one here
    "Text in video?",    # C  <- YOURS. yes / no / blank = auto
    "Audio in video?",   # D  <- YOURS. yes / no / blank = auto
    "-> Overlay",        # E  derived, so you can see what C means
    "-> Music",          # F  derived, so you can see what D means
    "Detected text",     # G  what the vision pass saw
    "Detected audio",    # H  measured peak, in dBFS
    "Variants used",     # I
    "Notes",             # J  yours
    "Framing",           # K  <- YOURS. crop / fit / blank = auto
    "-> Framing",        # L  derived, so you can see what K did
]

# crop / fit / anything else means "you decide"
FRAMING_CHOICES = ("crop", "fit")


def _framing(value):
    v = (value or "").strip().lower()
    return v if v in FRAMING_CHOICES else None

# Cells Marcus owns. The lane writes them ONCE, when it first sees a video, and
# never again — otherwise a later run would silently undo his correction.
VIDEO_USER_COLS = (2, 3)          # C, D
VIDEO_NOTES_COL = 9               # J

YES = ("yes", "y", "true", "1", "有")
NO = ("no", "n", "false", "0", "沒有", "没有")


def _tri(value):
    """'yes' -> True, 'no' -> False, anything else -> None (means: auto)."""
    v = (value or "").strip().lower()
    if v in YES:
        return True
    if v in NO:
        return False
    return None


def log(msg):
    print(f"[reel_sheet] {msg}", flush=True)


def _open_tab(title=None):
    from google_services import get_sheets_client
    gc = get_sheets_client()
    ss = gc.open_by_key(reel_config.REEL_SHEET_ID)
    title = title or reel_config.REEL_SHEET_TAB
    headers = {VIDEO_TAB: VIDEO_HEADERS,
               TASTE_TAB: TASTE_HEADERS}.get(title, HEADERS)
    try:
        return ss.worksheet(title)
    except Exception:
        ws = ss.add_worksheet(title=title, rows=400, cols=len(headers))
        ws.update(values=[headers], range_name="A1")
        return ws


def _split_caption(caption):
    """Return (body, hashtag line). The last line is always the tag line."""
    lines = [l for l in caption.split("\n")]
    if lines and lines[-1].strip().startswith("#"):
        return "\n".join(lines[:-1]).strip(), lines[-1].strip()
    return caption.strip(), ""


def build_row(number, filename, run):
    body, tags = _split_caption(run.get("caption", ""))
    overlay = run.get("overlay") or {}
    overlay_cell = ""
    if overlay:
        overlay_cell = (f"{overlay.get('treatment', '')} "
                        f"{overlay.get('contrast', '')}:1").strip()

    pattern = run.get("hook_pattern_id", "")
    if run.get("hook_pattern_name"):
        pattern = f"{pattern} {run['hook_pattern_name']}".strip()

    return [
        number,
        run.get("at", "").replace("T", " ")[:16],
        filename,
        run.get("variant", ""),
        run.get("hook", ""),
        pattern,
        run.get("hook_pattern_strength", ""),
        run.get("hook_mode", ""),
        overlay_cell,
        run.get("style", ""),
        body,
        tags,
        run.get("permalink", "") or run.get("media_id", ""),
    ]


def append_run(filename, run):
    """Add one published trial reel. Returns True on success, never raises."""
    try:
        ws = _open_tab()
        existing = len(ws.get_all_values())
        number = max(1, existing)          # header occupies row 1
        row = build_row(number, filename, run)
        ws.append_row(row, value_input_option="RAW",
                      table_range=f"A1:{chr(ord('A') + WRITTEN_COLS - 1)}1")
        log(f"mirrored row {number} to the Trial Reel sheet")
        return True
    except Exception as e:
        # Deliberately swallowed. See FAIL-OPEN above.
        log(f"WARNING: could not mirror to the sheet ({type(e).__name__}: "
            f"{str(e)[:160]}). The reel published fine; the row is missing. "
            f"Re-run `python3 reel_sheet.py --rebuild` to backfill.")
        return False


# ── the control tab: read and upsert ────────────────────────────────────────

def video_settings(filename):
    """Marcus's overrides for one video. Returns a dict, never raises.

    {"text": T/F/None, "audio": T/F/None, "framing": "crop"/"fit"/None,
     "found": bool}
    None means he has not answered, so the caller uses its own detection.
    A sheet failure returns all-None, which is exactly the same thing — the
    lane simply falls back to detecting for itself.
    """
    blank = {"text": None, "audio": None, "framing": None, "found": False}
    try:
        ws = _open_tab(VIDEO_TAB)
        rows = ws.get_all_values()
    except Exception as e:
        log(f"control tab unreadable ({type(e).__name__}) — auto-detecting")
        return blank

    for row in rows[1:]:
        if row and row[0].strip() == filename:
            return {
                "text": _tri(row[2] if len(row) > 2 else ""),
                "audio": _tri(row[3] if len(row) > 3 else ""),
                "framing": _framing(row[10] if len(row) > 10 else ""),
                "found": True,
            }
    return blank


def upsert_video(filename, detected, decisions, product="", variants=0):
    """Put a row in the control tab for this video. Never raises.

    Writes Marcus's two answer cells ONLY when creating the row, seeded from
    detection. On later runs it refreshes the derived and detected columns but
    LEAVES C and D alone — overwriting them would silently undo a correction,
    which is the whole reason the tab exists.
    """
    try:
        ws = _open_tab(VIDEO_TAB)
        rows = ws.get_all_values()

        derived = [
            "yes" if decisions.get("overlay") else "no",
            "yes" if decisions.get("music") else "no",
            "yes" if detected.get("text") else "no",
            (f"{detected['audio_dbfs']:.0f} dBFS"
             if detected.get("audio_dbfs") is not None else "none"),
            str(variants),
        ]

        for i, row in enumerate(rows[1:], start=2):
            if row and row[0].strip() == filename:
                # E-I only. C, D, J and K are his.
                ws.update(values=[derived], range_name=f"E{i}:I{i}",
                          value_input_option="RAW")
                if decisions.get("framing_note"):
                    ws.update(values=[[decisions["framing_note"]]],
                              range_name=f"L{i}", value_input_option="RAW")
                if product and (len(row) < 2 or not row[1].strip()):
                    ws.update(values=[[product]], range_name=f"B{i}",
                              value_input_option="RAW")
                return True

        # First sighting: seed his cells from what we detected, so the common
        # case needs no editing at all. A detection we do NOT have is left
        # blank — never written as "no", which would read as an answer.
        def tri_cell(value):
            return "" if value is None else ("yes" if value else "no")

        audio_known = (None if detected.get("audio_dbfs") is None
                              and detected.get("silent") is None
                       else not detected.get("silent"))
        ws.append_row(
            [filename, product,
             tri_cell(detected.get("text")),
             tri_cell(audio_known)] + derived
            # J Notes (his), K Framing (his) both blank; L is the derived note.
            + ["", "", decisions.get("framing_note", "")],
            value_input_option="RAW",
            table_range=f"A1:{chr(ord('A') + len(VIDEO_HEADERS) - 1)}1")
        log(f"added '{filename}' to the control tab")
        return True
    except Exception as e:
        log(f"could not update the control tab ({type(e).__name__}: "
            f"{str(e)[:120]}) — the reel is unaffected")
        return False


def _ensure_headers(ws, headers):
    """Widen an existing header row that predates a new column.

    The sheet was created with 17 columns; v2.1 needs 22, v2.5 needs 23. Rewriting only the
    header row is safe — no data cell moves.
    """
    try:
        current = ws.row_values(1)
        if len(current) < len(headers):
            try:
                if ws.col_count < len(headers):
                    ws.add_cols(len(headers) - ws.col_count)
            except Exception:
                pass
            ws.update(values=[headers], range_name="A1",
                      value_input_option="RAW")
    except Exception as e:
        log(f"could not widen the header row ({type(e).__name__})")


def _fmt_watch(ms):
    """ig_reels_avg_watch_time comes back in milliseconds."""
    try:
        return round(float(ms) / 1000.0, 1)
    except Exception:
        return ""


def write_metrics(run):
    """Put the newest reading for one published reel into its row.

    Keyed on the permalink (or media id) in column M, so it does not care what
    order rows are in or whether the sheet has been rebuilt since.

    A cell is written ONLY when there is a real number for it. That matters:
    an unreadable metric must leave whatever was there alone rather than
    stamping a 0, because 0 views and "we cannot see views" are opposite
    findings and the sheet must not confuse them.
    """
    import reel_metrics

    have = run.get("metrics") or {}
    if not have:
        return False

    # A real window outranks a probe, whatever order they were taken in: the
    # probe is a look at the wrong age and must never displace a measurement.
    import reel_metrics as _m
    label = None
    for lab, _ in reel_config.METRIC_WINDOWS:
        if lab in have:
            label = lab
    if label is None and _m.PROBE in have:
        label = _m.PROBE
    if label is None:
        return False
    reading = have[label]

    key = run.get("permalink", "") or run.get("media_id", "")
    if not key:
        return False

    try:
        ws = _open_tab()
        _ensure_headers(ws, HEADERS)
        rows = ws.get_all_values()
    except Exception as e:
        log(f"sheet unreadable ({type(e).__name__}) — metrics stay in "
            f"_state/reels.json only")
        return False

    target = None
    for i, row in enumerate(rows[1:], start=2):
        cell = row[PERMALINK_COL] if len(row) > PERMALINK_COL else ""
        if cell and (cell == key or cell == run.get("media_id", "")
                     or cell == run.get("permalink", "")):
            target = i
            break
    if target is None:
        log(f"no row found for {key} — run `python3 reel_sheet.py --rebuild` "
            f"first, then read metrics again")
        return False

    row = rows[target - 1]

    def existing(letter):
        idx = ord(letter) - ord("A")
        return row[idx] if len(row) > idx else ""

    cells = {}
    for metric, letter in METRIC_COLS.items():
        if reading.get(metric) is not None:
            cells[letter] = reading[metric]
    if reading.get("ig_reels_avg_watch_time") is not None:
        cells["U"] = _fmt_watch(reading["ig_reels_avg_watch_time"])
    stamp = reading.get("read_at", "")[:16].replace("T", " ")
    if label == _m.PROBE:
        age = reading.get("age_hours")
        shown = f"probe @{age}h" if age is not None else "probe"
    else:
        shown = label
    cells["V"] = (f"{shown} @ {stamp}" if reading.get("readable")
                  else f"{shown}: unreadable")

    try:
        # N:P and R:V as two writes, so Q is never touched.
        npp = [[cells.get(l, existing(l)) for l in ("N", "O", "P")]]
        ws.update(values=npp, range_name=f"N{target}:P{target}",
                  value_input_option="RAW")
        rv = [[cells.get(l, existing(l)) for l in ("R", "S", "T", "U", "V")]]
        ws.update(values=rv, range_name=f"R{target}:V{target}",
                  value_input_option="RAW")
        log(f"wrote {label} metrics into row {target}")
        return True
    except Exception as e:
        log(f"could not write metrics ({type(e).__name__}: {str(e)[:120]})")
        return False


def rebuild():
    """Rewrite every row from _state/reels.json.

    The state file is authoritative, so this can always restore the sheet —
    which is what makes it safe for append_run to fail quietly. Manual columns
    (Views/Likes/Comments/Notes) are preserved by keying on permalink/media id.
    """
    import reel_runner
    state = reel_runner.load_state()

    runs = []
    for h, rec in state["videos"].items():
        for run in rec.get("runs", []):
            runs.append((run.get("at", ""), rec.get("filename", h), run))
    runs.sort(key=lambda r: r[0])

    ws = _open_tab()
    _ensure_headers(ws, HEADERS)
    existing = ws.get_all_values()

    # Keep whatever Marcus typed in the manual columns, keyed by permalink.
    manual = {}
    for row in existing[1:]:
        if len(row) > WRITTEN_COLS and row[12]:
            manual[row[12]] = row[WRITTEN_COLS:]

    body = []
    for i, (_, filename, run) in enumerate(runs, start=1):
        row = build_row(i, filename, run)
        key = run.get("permalink", "") or run.get("media_id", "")
        row += manual.get(key, [])
        body.append(row)

    ws.clear()
    ws.update(values=[HEADERS] + body, range_name="A1",
              value_input_option="RAW")
    log(f"rebuilt {len(body)} row(s) from _state/reels.json")
    return len(body)


if __name__ == "__main__":
    import sys
    if "--rebuild" in sys.argv:
        n = rebuild()
        print(f"\nRebuilt {n} row(s).\n{reel_config.REEL_SHEET_URL}\n")
    else:
        print(f"\nTrial Reel sheet: {reel_config.REEL_SHEET_URL}")
        print("Run with --rebuild to rewrite every row from reels.json.\n")
