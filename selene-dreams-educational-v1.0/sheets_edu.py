# =============================================================================
# sheets_edu.py — gspread access for the Educational flow (both sheets)
# VERSION 1.4 — 2026-09-16
# CHANGELOG
#   1.4  2026-09-16  status_rows() also returns 'slides' = col P "Approved
#                    Slides" (review.gs v2.5 writes it; publish_edu 1.1 reads it).
#   1.3  2026-09-10  tab()/values() route by tab name: Image Library and Sources
#                    now live in their own spreadsheet (C.IMAGE_LIBRARY_SHEET_ID);
#                    callers are unchanged.
#   1.2  2026-09-10  topics_rows reads the hidden visual briefs (Post Topic N-T);
#                    queue_rows reads the candidates JSON (Generation Queue T).
#   1.1  2026-09-10  QUOTA FIX. edu_sheet() called open_by_key on EVERY access,
#                    and tab() then fetched the worksheet list again - so one
#                    set_status cost two or three metadata READS before its one
#                    write, and a tick with a few dozen status writes blew the
#                    60-reads-per-minute quota on metadata alone (429s all day,
#                    shared with the v3.0 lane's launchd jobs). Spreadsheet and
#                    worksheet handles are now cached for the life of the
#                    process, and get_all_values is cached per tab for a few
#                    seconds and dropped the moment that tab is written.
#                    Also one retry on a dropped keep-alive: the cached session
#                    idles through a five-minute Claude call, Google closes it,
#                    and the first Sheets call after that died with "Remote end
#                    closed connection" - which cost #16 its finished caption.
#   1.0  2026-08-28  First release.
# =============================================================================
import datetime, time, gspread
import config_edu as C

VALUES_TTL = 12.0     # seconds a tab's values stay cached between reads

_gc = None
_sheets = {}          # sheet id -> Spreadsheet
_tabs = {}            # (sheet id, tab name) -> Worksheet
_values = {}          # (sheet id, tab name) -> (ts, rows)


def gc():
    global _gc
    if _gc is None:
        _gc = gspread.service_account(filename=C.CREDENTIALS_PATH)
    return _gc


_WRITES = ("update", "update_acell", "update_cell", "update_cells", "append_row",
           "append_rows", "batch_update", "delete_rows", "insert_rows", "clear")


class _Tab:
    """Worksheet proxy: any write drops that tab's cached values, so a stage
    that writes then re-reads in the same tick never sees stale rows."""
    def __init__(self, ws, key, name):
        self._ws, self._key, self._name = ws, key, name

    def __getattr__(self, attr):
        f = getattr(self._ws, attr)
        if attr in _WRITES:
            def wrapped(*a, **kw):
                r = _retry(f, *a, **kw)
                invalidate(self._name, self._key)
                return r
            return wrapped
        if attr in ("acell", "cell", "get", "get_all_values", "get_values", "row_values", "col_values"):
            return lambda *a, **kw: _retry(f, *a, **kw)
        return f


def _retry(f, *a, **kw):
    """One retry on a dropped keep-alive. The cached session sits idle through a
    five-minute Claude call, and Google closes it; the first request after
    that dies with 'Remote end closed connection without response'."""
    import requests
    try:
        return f(*a, **kw)
    except (requests.exceptions.ConnectionError, ConnectionResetError, BrokenPipeError):
        time.sleep(2)
        return f(*a, **kw)


class _Sheet:
    def __init__(self, ss, key):
        self._ss, self._key = ss, key

    def worksheet(self, name):
        return _ws(self._key, name)

    def worksheets(self):
        return self._ss.worksheets()

    def __getattr__(self, attr):
        return getattr(self._ss, attr)


def _sheet(key):
    if key not in _sheets:
        _sheets[key] = _Sheet(gc().open_by_key(key), key)
    return _sheets[key]


def edu_sheet(): return _sheet(C.EDU_QUEUE_SHEET_ID)
def topic_sheet(): return _sheet(C.POST_TOPIC_SHEET_ID)


def _ws(key, name):
    k = (key, name)
    if k not in _tabs:
        _tabs[k] = _Tab(_sheet(key)._ss.worksheet(name), key, name)
    return _tabs[k]


def _key_for(name):
    """Which spreadsheet a tab name lives in. The Image Library and Sources
    tabs are brand content in their own spreadsheet; everything else is the
    edu queue sheet."""
    if name in (C.TAB_LIBRARY, C.TAB_SOURCES):
        return C.IMAGE_LIBRARY_SHEET_ID
    return C.EDU_QUEUE_SHEET_ID


def tab(name):
    """Worksheet by tab name, routed to the right spreadsheet (cached handle;
    writes through it drop the tab's value cache automatically)."""
    return _ws(_key_for(name), name)


def invalidate(name=None, key=None):
    key = key or (_key_for(name) if name else C.EDU_QUEUE_SHEET_ID)
    if name is None:
        _values.clear()
    else:
        _values.pop((key, name), None)


def values(name, key=None):
    """get_all_values with a short cache, so a stage that asks for the same tab
    five times in one tick reads it once."""
    key = key or _key_for(name)
    k = (key, name)
    hit = _values.get(k)
    if hit and time.time() - hit[0] < VALUES_TTL:
        return hit[1]
    rows = _ws(key, name).get_all_values()
    _values[k] = (time.time(), rows)
    return rows


def topics_rows():
    """Post Topic 'Topics' tab as list of dicts (row index included, 1-based)."""
    vals = values(C.TAB_TOPICS, key=C.POST_TOPIC_SHEET_ID)
    out = []
    for i, r in enumerate(vals[1:], start=2):
        r = (r + [""] * 20)[:20]
        out.append({"row": i, "num": r[0], "type": r[1], "desc": r[2],
                    "slides": [s for s in r[3:10]], "status": r[10],
                    "post_url": r[11], "remark": r[12],
                    "briefs": [s for s in r[13:20]]})      # N-T, hidden
    return out


def queue_rows():
    vals = values(C.TAB_QUEUE)
    out = []
    for i, r in enumerate(vals[1:], start=2):
        r = (r + [""] * 20)[:20]
        out.append({"row": i, "num": r[0], "year": r[1], "month": r[2], "topic": r[3],
                    "type": r[4], "series": r[5], "sources": r[6:13], "mix": r[13],
                    "credits": r[14], "folder": r[15], "urls": r[16],
                    "carousel": r[17], "notes": r[18], "candidates": r[19]})
    return out


def status_rows():
    vals = values(C.TAB_STATUS)
    out = []
    for i, r in enumerate(vals[C.STATUS_HEADER_ROW:], start=C.STATUS_HEADER_ROW + 1):
        r = (r + [""] * 16)[:16]
        out.append({"row": i, "num": r[1], "topic": r[2], "words": r[3], "render": r[4],
                    "caption": r[7], "post": r[10], "sched": r[11],
                    "slides": r[15]})     # P "Approved Slides" (review.gs v2.5)
    return out


def now_hkt():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def add_remark(status_row, kind, msg):
    """Append-only system remark, v3.0 format: '[ts] KIND: msg' joined with ' | '."""
    ws = tab(C.TAB_STATUS)
    cell = f"N{status_row}"
    cur = ws.acell(cell).value or ""
    entry = f"[{now_hkt()}] {kind}: {msg}"
    ws.update_acell(cell, (cur + " | " + entry) if cur else entry)
    invalidate(C.TAB_STATUS)


def set_status(status_row, col_letter, value):
    tab(C.TAB_STATUS).update_acell(f"{col_letter}{status_row}", value)
    invalidate(C.TAB_STATUS)
