"""
reel_feedback.py — read what Marcus said about published reels, and remember it
=============================================================================
VERSION 1.1 — 2026-09-16

WHAT THIS IS
    The reel lane's LEARNING INPUT. Until now the only way Marcus's taste
    reached the hook and caption writers was a hand-edit to the prompts after
    a bad post (the 2026-09-10 "make an entrance" fix). This module gives him
    two places to write, both in the sheet he already opens, and turns them
    into a block the writers read on every run:

      1. Trial Reels tab, per published reel:
           Q  Notes    — free text ("too poetic", "this one, more of this")
           W  Rating   — 1 to 5
         The row already carries the hook, pattern, style and mode, so a note
         has its context without him typing any of it.

      2. Taste Notes tab, not tied to a post:
           A Date · B Note · C Applies to · D Seen
         "fewer japandi rooms", "more hands in frame", "captions shorter".
         D is stamped by the lane the first time it reads a row, so he can see
         it landed.

THE ONE RULE
    Feedback changes HOW a reel is written. It NEVER decides WHETHER a reel
    publishes. This lane was built with no approval step, by request, and a
    taste file must not become one by the back door. Concretely:
      - the taste block goes into the writer prompts as context;
      - a pattern Marcus has rated badly (avg <= FEEDBACK_LOW_RATING over at
        least FEEDBACK_MIN_RATINGS ratings) is dropped from the ROTATION,
        never from publishing — if every pattern is rated badly the rotation
        falls back to all of them;
      - nothing here can raise into the runner, and nothing here can park a
        video.

FAIL-OPEN, LIKE THE CONTROL TAB
    Reading a sheet reintroduces a Google dependency into a lane that was
    deliberately built without one. Same resolution as reel_sheet v2.0: the
    sheet is read when reachable, and what was read is kept in
    _state/reels.json under "feedback". Sheet down -> the writers see the
    LAST feedback that was read, not nothing, and the reel publishes anyway.
    Every public function swallows its own errors.

WHAT GETS WRITTEN
    - state["feedback"]           the ingested items (source of truth)
    - reel_config.TASTE_PATH      a human-readable reel-taste.md, regenerated
                                  from state on every sync so Marcus can read
                                  what the writers are being told
    - Taste Notes tab, column D   the "Seen" stamp (fail-open)

CHANGELOG
    1.1  2026-09-16  THE POSTED CONTENT SHEET. Marcus asked for one sheet for
                     every published post. Reel ratings/notes are now read
                     from there FIRST (posted_sheet.read_feedback, lane
                     reels), with the Trial Reels tab's Q/W still honoured so
                     nothing already typed is lost. Taste Notes are read from
                     the new sheet's tab; the old tab is a fallback.
    1.0  2026-09-16  First build. Marcus asked where to leave comments so the
                     lane "can slowly learn and adapt"; decided on sheet
                     columns + a Taste Notes tab over a central feedback tab
                     or chat commands, because the row already has the context
                     and it works from his phone.
=============================================================================
"""

import hashlib
import os
from datetime import datetime

import reel_config

VERSION = "1.0"

# Taste Notes tab layout. D is the only column the lane writes.
TASTE_TAB = getattr(reel_config, "TASTE_TAB", "Taste Notes")
TASTE_HEADERS = ["Date", "Note", "Applies to", "Seen"]
TASTE_SEEN_COL = "D"

# Which scopes a note in "Applies to" can carry. Blank = all lanes. The reel
# lane reads reel + all; the image and educational lanes can read the same
# tab for their own scope later without a schema change.
SCOPE_ALL = ("", "all", "everything", "any")
SCOPE_REEL = ("reel", "reels", "trial reel", "trial reels", "video", "videos")

MAX_ITEMS = getattr(reel_config, "FEEDBACK_MAX_ITEMS", 12)
MAX_CHARS = getattr(reel_config, "FEEDBACK_MAX_CHARS", 2400)
LOW_RATING = getattr(reel_config, "FEEDBACK_LOW_RATING", 2.0)
MIN_RATINGS = getattr(reel_config, "FEEDBACK_MIN_RATINGS", 2)


def log(msg):
    print(f"[reel_feedback] {msg}", flush=True)


def _now():
    return datetime.now().isoformat(timespec="minutes")


def _rating(value):
    """'4' -> 4.0, '4/5' -> 4.0, anything else -> None. Never raises."""
    v = (value or "").strip()
    if not v:
        return None
    v = v.split("/")[0].strip()
    try:
        r = float(v)
    except ValueError:
        return None
    return r if 1 <= r <= 5 else None


def _scope_is_reel(value):
    v = (value or "").strip().lower()
    return v in SCOPE_ALL or v in SCOPE_REEL


def _col(letter):
    return ord(letter.upper()) - ord("A")


# ── reading ─────────────────────────────────────────────────────────────────

def _runs_by_key(state):
    """permalink / media id -> (filename, run)."""
    out = {}
    for rec in (state.get("videos") or {}).values():
        for run in rec.get("runs", []):
            for k in (run.get("permalink"), run.get("media_id")):
                if k:
                    out[k] = (rec.get("filename", ""), run)
    return out


def read_reel_rows(state):
    """Notes + ratings from the Trial Reels tab, joined to the runs in state.

    Returns a list of feedback items, or None if the sheet was unreachable.
    Never raises.
    """
    try:
        import reel_sheet
        ws = reel_sheet._open_tab()
        rows = ws.get_all_values()
    except Exception as e:
        log(f"Trial Reels tab unreadable ({type(e).__name__}) — keeping the "
            f"feedback already in state")
        return None

    try:
        import reel_sheet
        headers = rows[0] if rows else []
        notes_i = headers.index("Notes") if "Notes" in headers else _col("Q")
        rating_i = (headers.index("Rating") if "Rating" in headers
                    else _col(reel_sheet.RATING_COL))
        key_i = reel_sheet.PERMALINK_COL
    except Exception:
        notes_i, rating_i, key_i = _col("Q"), _col("W"), _col("M")

    runs = _runs_by_key(state)
    items = []
    for row in rows[1:]:
        key = row[key_i].strip() if len(row) > key_i else ""
        if not key:
            continue
        note = row[notes_i].strip() if len(row) > notes_i else ""
        rating = _rating(row[rating_i] if len(row) > rating_i else "")
        if not note and rating is None:
            continue
        filename, run = runs.get(key, ("", {}))
        items.append({
            "kind": "reel",
            "key": key,
            "video": filename or (row[2] if len(row) > 2 else ""),
            "hook": run.get("hook") or (row[4] if len(row) > 4 else ""),
            "pattern_id": run.get("hook_pattern_id")
                          or (row[5].split(" ")[0] if len(row) > 5 else ""),
            "pattern_name": run.get("hook_pattern_name", ""),
            "style": run.get("style") or (row[9] if len(row) > 9 else ""),
            "mode": run.get("hook_mode") or (row[7] if len(row) > 7 else ""),
            "published": run.get("at", "")[:10]
                         or (row[1][:10] if len(row) > 1 else ""),
            "rating": rating,
            "note": note,
        })
    return items


def _posted_reel_rows(state):
    """Reel notes/ratings from the Posted Content sheet, joined to runs.
    None if unreachable. Never raises."""
    try:
        import posted_sheet
        rows = posted_sheet.read_feedback()
    except Exception as e:
        log(f"posted sheet unavailable ({type(e).__name__})")
        return None
    if rows is None:
        return None
    runs = _runs_by_key(state)
    out = []
    for r in rows:
        if r.get("lane") != "reels":
            continue
        filename, run = runs.get(r["key"], ("", {}))
        out.append({
            "kind": "reel", "key": r["key"], "video": filename,
            "hook": run.get("hook") or r.get("what", ""),
            "pattern_id": run.get("hook_pattern_id")
                          or (r.get("choices", "").split(",")[0].strip()),
            "pattern_name": run.get("hook_pattern_name", ""),
            "style": run.get("style", ""), "mode": run.get("hook_mode", ""),
            "published": run.get("at", "")[:10] or r.get("when", ""),
            "rating": r.get("rating"), "note": r.get("note", ""),
        })
    return out


def read_taste_rows():
    """Free-text directions from the Taste Notes tab — the Posted Content
    sheet's tab first, the Trial Reel sheet's tab as fallback.

    Returns (items, unseen_row_numbers) or (None, []) if unreachable.
    Never raises. Rows whose scope is not reel/all are skipped but still
    stamped as seen, so Marcus is not left wondering.
    """
    rows = None
    try:
        import posted_sheet
        ws = posted_sheet._open(posted_sheet.TASTE_TAB)
        rows = ws.get_all_values()
        _STAMP_TARGET[0] = "posted"
    except Exception as e:
        log(f"posted Taste Notes unreadable ({type(e).__name__}) — trying the "
            f"Trial Reel sheet's tab")
    if rows is None:
        try:
            import reel_sheet
            ws = reel_sheet._open_tab(TASTE_TAB)
            rows = ws.get_all_values()
            _STAMP_TARGET[0] = "reel"
        except Exception as e:
            log(f"Taste Notes tab unreadable ({type(e).__name__}) — keeping the "
                f"notes already in state")
            return None, []

    items, unseen = [], []
    for i, row in enumerate(rows[1:], start=2):
        note = row[1].strip() if len(row) > 1 else ""
        if not note:
            continue
        date = row[0].strip() if len(row) > 0 else ""
        scope = row[2].strip() if len(row) > 2 else ""
        seen = row[3].strip() if len(row) > 3 else ""
        if not seen:
            unseen.append(i)
        if not _scope_is_reel(scope):
            continue
        key = "taste:" + hashlib.sha1(
            f"{date}|{note}|{scope}".encode()).hexdigest()[:12]
        items.append({
            "kind": "taste",
            "key": key,
            "date": date,
            "note": note,
            "scope": scope or "all",
        })
    return items, unseen


_STAMP_TARGET = ["posted"]      # which sheet the last taste read came from


def _stamp_seen(rows_to_stamp):
    """Write today's date into column D for rows the lane just ingested."""
    if not rows_to_stamp:
        return 0
    try:
        if _STAMP_TARGET[0] == "posted":
            import posted_sheet
            ws = posted_sheet._open(posted_sheet.TASTE_TAB)
        else:
            import reel_sheet
            ws = reel_sheet._open_tab(TASTE_TAB)
        stamp = _now()[:16].replace("T", " ")
        for i in rows_to_stamp:
            ws.update(values=[[stamp]], range_name=f"{TASTE_SEEN_COL}{i}",
                      value_input_option="RAW")
        return len(rows_to_stamp)
    except Exception as e:
        log(f"could not stamp Seen on the Taste Notes tab "
            f"({type(e).__name__}) — the notes were still read")
        return 0


# ── the sync ────────────────────────────────────────────────────────────────

def sync(state):
    """Pull new feedback into state["feedback"]. Returns True if anything
    changed. Never raises; a sheet failure leaves the old feedback in place.
    """
    try:
        fb = state.setdefault("feedback", {"items": {}, "synced_at": ""})
        items = fb.setdefault("items", {})
        changed = False

        reel_items = read_reel_rows(state)
        posted = _posted_reel_rows(state)
        if posted is not None:
            # The new sheet wins for a permalink present in both.
            merged = {it["key"]: it for it in (reel_items or [])}
            merged.update({it["key"]: it for it in posted})
            reel_items = list(merged.values())
        if reel_items is not None:
            for it in reel_items:
                old = items.get(it["key"])
                if old is None or old.get("note") != it["note"] \
                        or old.get("rating") != it["rating"]:
                    it["seen_at"] = _now()
                    items[it["key"]] = it
                    changed = True
            # A note that was cleared in the sheet is withdrawn here too.
            present = {it["key"] for it in reel_items}
            for k in [k for k, v in items.items()
                      if v.get("kind") == "reel" and k not in present]:
                del items[k]
                changed = True

        taste_items, unseen = read_taste_rows()
        if taste_items is not None:
            for it in taste_items:
                if it["key"] not in items:
                    it["seen_at"] = _now()
                    items[it["key"]] = it
                    changed = True
            present = {it["key"] for it in taste_items}
            for k in [k for k, v in items.items()
                      if v.get("kind") == "taste" and k not in present]:
                del items[k]
                changed = True
            if unseen:
                _stamp_seen(unseen)

        if reel_items is not None or taste_items is not None:
            fb["synced_at"] = _now()
        if changed:
            n_reel = sum(1 for v in items.values() if v.get("kind") == "reel")
            n_taste = len(items) - n_reel
            log(f"feedback: {n_reel} reel note(s)/rating(s), {n_taste} taste "
                f"note(s)")
            write_taste_file(state)
        return changed
    except Exception as e:
        log(f"WARNING: feedback sync failed ({type(e).__name__}: "
            f"{str(e)[:120]}) — the reel is unaffected")
        return False


# ── what the writers see ────────────────────────────────────────────────────

def pattern_scores(state):
    """{pattern_id: (avg, n)} from rated reels. Never raises."""
    scores = {}
    try:
        for it in (state.get("feedback") or {}).get("items", {}).values():
            if it.get("kind") != "reel" or it.get("rating") is None:
                continue
            pid = it.get("pattern_id") or ""
            if not pid:
                continue
            tot, n = scores.get(pid, (0.0, 0))
            scores[pid] = (tot + it["rating"], n + 1)
        return {p: (round(t / n, 2), n) for p, (t, n) in scores.items()}
    except Exception:
        return {}


def low_rated_patterns(state):
    """Pattern ids Marcus has consistently rated badly. Rotation drops them;
    publishing does not care."""
    out = []
    for pid, (avg, n) in pattern_scores(state).items():
        if n >= MIN_RATINGS and avg <= LOW_RATING:
            out.append(pid)
    return out


def style_scores(state):
    scores = {}
    try:
        for it in (state.get("feedback") or {}).get("items", {}).values():
            if it.get("kind") != "reel" or it.get("rating") is None:
                continue
            s = it.get("style") or ""
            if not s:
                continue
            tot, n = scores.get(s, (0.0, 0))
            scores[s] = (tot + it["rating"], n + 1)
        return {s: (round(t / n, 2), n) for s, (t, n) in scores.items()}
    except Exception:
        return {}


def taste_block(state, for_stage="hook"):
    """The text the hook and caption prompts receive. Bounded. Never raises.

    for_stage is "hook" or "caption"; it only changes the framing sentence.
    """
    try:
        items = list((state.get("feedback") or {}).get("items", {}).values())
        if not items:
            return ("(No feedback from Marcus yet. Write to the brand "
                    "territory above.)")

        taste = [i for i in items if i.get("kind") == "taste"]
        reels = [i for i in items if i.get("kind") == "reel"]
        reels.sort(key=lambda i: i.get("seen_at", ""), reverse=True)
        reels = reels[:MAX_ITEMS]

        lines = []
        if taste:
            lines.append("STANDING DIRECTIONS (apply to every reel):")
            for t in taste:
                lines.append(f"  - {t['note']}")
            lines.append("")
        if reels:
            lines.append("WHAT HE SAID ABOUT SPECIFIC PUBLISHED REELS "
                         "(newest first; 5 = exactly right, 1 = wrong):")
            for r in reels:
                bits = []
                if r.get("rating") is not None:
                    bits.append(f"rated {r['rating']:.0f}/5")
                if r.get("note"):
                    bits.append(f'"{r["note"]}"')
                ctx = f"{r.get('pattern_id') or '?'}"
                if r.get("style"):
                    ctx += f", {r['style']}"
                if r.get("mode"):
                    ctx += f", {r['mode']}"
                lines.append(f'  - hook "{r.get("hook", "")}" ({ctx}): '
                             + "; ".join(bits))
            lines.append("")
        ps = pattern_scores(state)
        ss = style_scores(state)
        if ps or ss:
            lines.append("AVERAGE RATINGS SO FAR:")
            for pid, (avg, n) in sorted(ps.items()):
                lines.append(f"  pattern {pid}: {avg} over {n}")
            for s, (avg, n) in sorted(ss.items()):
                lines.append(f"  style {s}: {avg} over {n}")
        text = "\n".join(lines).strip()
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS].rsplit("\n", 1)[0] + "\n  (older feedback trimmed)"
        return text
    except Exception as e:
        return f"(feedback unavailable this run: {type(e).__name__})"


def write_taste_file(state):
    """Regenerate reel-taste.md so Marcus can read what the writers are told.
    Derived from state, never read back. Never raises."""
    try:
        path = reel_config.TASTE_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fb = state.get("feedback") or {}
        body = (
            "# Reel taste — what the hook and caption writers are told\n\n"
            f"Generated by reel_feedback.py {VERSION} from _state/reels.json. "
            f"Last sheet sync: {fb.get('synced_at') or 'never'}.\n"
            "Do not edit here — write in the Trial Reel sheet (Notes / Rating "
            "on a row, or the Taste Notes tab). This file is regenerated.\n\n"
            "## Block injected into the prompts\n\n```\n"
            + taste_block(state) + "\n```\n\n"
            "## Rotation effect\n\n"
        )
        low = low_rated_patterns(state)
        body += ("Patterns dropped from rotation (avg <= "
                 f"{LOW_RATING} over >= {MIN_RATINGS} ratings): "
                 + (", ".join(low) if low else "none") + "\n")
        body += ("\nFeedback never decides whether a reel publishes. "
                 "It changes how the next one is written.\n")
        tmp = path + ".tmp"
        with open(tmp, "w") as fh:
            fh.write(body)
        os.replace(tmp, path)
        return True
    except Exception as e:
        log(f"could not write {getattr(reel_config, 'TASTE_PATH', '?')} "
            f"({type(e).__name__})")
        return False


def report(state):
    """--feedback: print what the writers will see."""
    fb = state.get("feedback") or {}
    print(f"\nFEEDBACK — last synced {fb.get('synced_at') or 'never'}\n")
    print(taste_block(state))
    low = low_rated_patterns(state)
    print(f"\nPatterns dropped from rotation: {', '.join(low) or 'none'}")
    print(f"Taste file: {reel_config.TASTE_PATH}\n")


if __name__ == "__main__":
    import sys
    import reel_runner
    state = reel_runner.load_state()
    if "--sync" in sys.argv:
        if sync(state):
            reel_runner.save_state(state)
            print("feedback updated")
        else:
            print("no change")
    report(state)
