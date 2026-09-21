#!/usr/bin/env python3
"""Read the Selene social / discount calendar.

The calendar is a SEPARATE spreadsheet from the Generation Queue:
  https://docs.google.com/spreadsheets/d/1WoIDort5Kb_zn6qDi7MheoDlo_XQ-9zHD75ltGrbTm0
  tab "2026" — Date Start | Date End | Event Name | Offer Type |
               Discount / Value | Applies To | Promo Message / Notes

Dates are stored as PLAIN TEXT ("Aug 1") with no year, so they are read as
display strings and the year comes from the tab name.

ACCESS: this uses the same service account as everything else
(selene-dreams-script@selene-dreams.iam.gserviceaccount.com). The calendar
spreadsheet must be shared with that address, at Viewer, or every call here
returns [] — deliberately, so a permissions gap degrades the research run
rather than failing it.

Standalone check:  python3 social_calendar.py
"""
import datetime
import re

import google_services

CAL_SHEET_ID = "1WoIDort5Kb_zn6qDi7MheoDlo_XQ-9zHD75ltGrbTm0"
CAL_TAB = "2026"
LOOKAHEAD_DAYS = 21          # research → picks → prompts → images → publish

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun",
          "jul", "aug", "sep", "oct", "nov", "dec"]


def _parse(value, year):
    """'Aug 1' / 'Aug 1, 2026' / '8/1/2026' / '2026-08-01' → date, or None."""
    t = str(value or "").strip()
    if not t:
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"^([A-Za-z]{3,})\.?\s+(\d{1,2})(?:\s*,\s*(\d{4}))?$", t)
    if m:
        mon = m.group(1)[:3].lower()
        if mon not in MONTHS:
            return None
        return datetime.date(int(m.group(3) or year), MONTHS.index(mon) + 1,
                             int(m.group(2)))
    m = re.match(r"^(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?$", t)
    if m:
        y = m.group(3) or str(year)
        if len(y) == 2:
            y = "20" + y
        return datetime.date(int(y), int(m.group(1)), int(m.group(2)))
    return None


def load_events(logger=None):
    """Every dated event in the calendar, chronological. [] on any failure."""
    def log(msg):
        if logger:
            logger(msg)
    try:
        year = int(CAL_TAB)
    except ValueError:
        year = datetime.date.today().year
    try:
        client = google_services.get_sheets_client()
        ws = client.open_by_key(CAL_SHEET_ID).worksheet(CAL_TAB)
        rows = ws.get_all_values()
    except Exception as e:
        log(f"  NOTE: social calendar unavailable ({e}) — continuing without it. "
            f"Share the sheet with the service account if this persists.")
        return []

    out = []
    for r in rows[1:]:                       # row 1 is the header
        r = list(r) + [""] * (7 - len(r))
        name = str(r[2]).strip()
        start = _parse(r[0], year)
        if not name or not start:
            continue
        end = _parse(r[1], year) or start
        if end < start:
            end = start
        out.append({
            "start": start, "end": end, "name": name,
            "type": str(r[3]).strip(), "value": str(r[4]).strip(),
            "applies": str(r[5]).strip(), "notes": str(r[6]).strip(),
        })
    out.sort(key=lambda e: e["start"])
    return out


def upcoming(days=LOOKAHEAD_DAYS, today=None, logger=None):
    """Events overlapping the window from today to today+days."""
    today = today or datetime.date.today()
    horizon = today + datetime.timedelta(days=days)
    return [e for e in load_events(logger=logger)
            if e["end"] >= today and e["start"] <= horizon]


def as_prompt_block(days=LOOKAHEAD_DAYS, today=None, logger=None):
    """The block injected into the phase-4 research prompt.

    Returns a sentence saying there is nothing rather than an empty string,
    so the agent can tell "no promotions" from "the calendar failed to load"
    and never invents a promotion it cannot see.
    """
    today = today or datetime.date.today()
    evs = upcoming(days=days, today=today, logger=logger)
    if not evs:
        return ("No promotions are scheduled in the next "
                f"{days} days (or the calendar could not be read — in that "
                "case say so rather than assuming a quiet period).")
    lines = []
    for e in evs:
        when = e["start"].strftime("%b %d")
        if e["end"] != e["start"]:
            when += " – " + e["end"].strftime("%b %d")
        bits = [b for b in (e["type"], e["value"], e["applies"]) if b]
        lines.append(f"- {when} · {e['name']}" +
                     (" · " + " · ".join(bits) if bits else "") +
                     (f" · {e['notes']}" if e["notes"] else ""))
    return (f"Promotions running or starting within {days} days of {today}:\n"
            + "\n".join(lines))


if __name__ == "__main__":
    evs = load_events(logger=print)
    print(f"{len(evs)} event(s) in the calendar")
    for e in evs[:5]:
        print("  ", e["start"], "→", e["end"], e["name"], "|", e["type"], e["value"])
    print()
    print(as_prompt_block(logger=print))
