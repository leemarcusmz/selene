"""
taste_store.py — ONE taste layer for all three lanes
=============================================================================
VERSION 1.3 — 2026-09-16

THE DECISION (Marcus, 2026-09-16)
    Keep the image, educational and reel flows SEPARATE — the flows differ —
    but make what they learn about his taste COMMUNICABLE: one place where
    references, feedback and outcomes from every lane accumulate, that every
    writer can read. Until now: the screener learned from picks, the reel
    lane from its sheet, the educational lane from nothing, and none of it
    crossed a lane boundary.

WHERE
    The selene-ig-memory GitHub repo, folder taste/. Every lane already
    clones it (clone_memory), pushes to it (pipeline_state.push_with_retry),
    and the Apps Script pages and the cloud research agent already read it.
    No new infrastructure.

WHAT IT WRITES (all machine-generated, regenerated whole on every sync so
the newest read of a source always wins — never appended to by hand):
    taste/references.md   every reference image + its vision note, by lane
                          (from reference_drive's manifest)
    taste/feedback.md     every note/rating Marcus or the team left, any lane:
                          reel rows (Q/W), image-lane "User Remark(s)" (GS N),
                          educational "User" (GS O), the Taste Notes tab
    taste/outcomes.md     what performed: reels (reel_metrics) + carousels
                          (post_metrics), with the choices behind each post
    taste/*.json          the same data, for code
    taste/brief.md        NOT written here — that is the distill step (next
                          build). Writers read brief.md; this module feeds it.

THE RULE, unchanged
    Taste changes HOW things are written, never WHETHER they publish.

RATE LIMIT
    Sources change slowly and a git push every 15 minutes is noise. The reel
    tick calls maybe_sync(), which syncs at most every SYNC_EVERY_HOURS;
    `python3 taste_store.py --sync` forces one.

CHANGELOG
    1.3  2026-09-16  Reference SETS (reference_drive 1.1): a folder of
                     screenshots that is one post becomes ONE row in
                     references.md carrying its structure note and Marcus's
                     own folder note; its slides no longer appear as
                     undescribed singles. Also fixed VERSION constant, which
                     had stayed at "1.0" through 1.1 and 1.2.
    1.2  2026-09-16  THE POSTED CONTENT SHEET is now the primary feedback
                     source: ratings/notes for every lane incl. hand-posted
                     ("manual") rows, and Taste Notes of EVERY scope (the
                     reel state only kept reel/all-scoped ones, so an
                     "images" direction never reached the brief — fixed).
                     The old per-lane columns still feed.
    1.1  2026-09-16  sync() refreshes the local brief cache from the clone, so
                     a brief distilled elsewhere reaches this Mac's writers.
    1.0  2026-09-16  First build: collectors for all three lanes, the three
                     files, rate-limited sync from the reel tick.
=============================================================================
"""

import json
import os
import shutil
import tempfile
import time
from datetime import datetime

import config
import reel_config

VERSION = "1.3"
TASTE_DIR = "taste"
SYNC_EVERY_HOURS = getattr(config, "TASTE_SYNC_EVERY_HOURS", 6)
STAMP_PATH = os.path.join(reel_config.BASE_DIR, "_state", "taste-sync.stamp")


def log(msg):
    print(f"[taste_store] {msg}", flush=True)


def _now():
    return datetime.now().isoformat(timespec="minutes")


# =============================================================================
# COLLECTORS — each returns a list of dicts and never raises
# =============================================================================

def collect_references():
    out = []
    try:
        import reference_drive as rd
        m = rd.load_manifest()
        for fid, v in m.get("files", {}).items():
            if not v.get("downloaded") or v.get("set"):
                continue                      # set slides are rolled up below
            note = v.get("note") or {}
            out.append({
                "lane": v.get("lane", "style"), "name": v.get("name", ""),
                "added": v.get("added_at", ""), "shows": note.get("shows", ""),
                "on_brand": note.get("on_brand", ""),
                "borrow": note.get("borrow", ""),
            })
        for sid, s in m.get("sets", {}).items():
            note = s.get("note") or {}
            shows = note.get("shows", "")
            if note.get("structure"):
                shows = f"{shows} Structure: {note['structure']}".strip()
            if s.get("marcus_note"):
                shows = f'Marcus: "{s["marcus_note"]}" {shows}'.strip()
            out.append({
                "lane": s.get("lane", "educational"),
                "name": f"SET {s.get('name', '')} ({len(s.get('files') or [])} slides)",
                "added": s.get("added_at", ""), "shows": shows,
                "on_brand": note.get("on_brand", ""),
                "borrow": note.get("borrow", ""),
            })
        out.sort(key=lambda r: r.get("added", ""), reverse=True)
    except Exception as e:
        log(f"references unavailable ({type(e).__name__})")
    return out


def _reel_feedback():
    out = []
    try:
        import reel_runner
        state = reel_runner.load_state()
        for it in (state.get("feedback") or {}).get("items", {}).values():
            if it.get("kind") == "reel":
                out.append({
                    "lane": "reels", "when": it.get("seen_at", "")[:10],
                    "about": f'hook "{it.get("hook", "")}"',
                    "choices": ", ".join(x for x in (
                        it.get("pattern_id"), it.get("style"), it.get("mode"))
                        if x),
                    "rating": it.get("rating"), "note": it.get("note", ""),
                    "ref": it.get("key", ""),
                })
            elif it.get("kind") == "taste":
                out.append({
                    "lane": it.get("scope", "all"), "when": it.get("date", ""),
                    "about": "standing direction", "choices": "",
                    "rating": None, "note": it.get("note", ""),
                    "ref": "Taste Notes tab",
                })
    except Exception as e:
        log(f"reel feedback unavailable ({type(e).__name__})")
    return out


def _sheet_values(sheet_id, tab):
    from google_services import get_sheets_client
    return get_sheets_client().open_by_key(sheet_id).worksheet(tab).get_all_values()


def _image_feedback():
    """Generation Status col N 'User Remark(s)', with what the row was."""
    out = []
    try:
        vals = _sheet_values(config.GOOGLE_SHEET_ID, config.GS_SHEET_NAME)
    except Exception as e:
        log(f"image-lane sheet unavailable ({type(e).__name__})")
        return out
    try:
        queue = _sheet_values(config.GOOGLE_SHEET_ID, config.GOOGLE_SHEET_NAME)
    except Exception:
        queue = []
    for i, r in enumerate(vals, start=1):
        if i < config.GS_FIRST_DATA_ROW:
            continue
        cell = lambda c: str(r[c - 1]).strip() if len(r) >= c else ""
        note = cell(config.GS_COL_USER_REMARK)
        num = cell(config.GS_COL_NUMBER)
        if not note or not num.isdigit():
            continue
        product = ""
        try:
            q = queue[int(num)] if len(queue) > int(num) else []
            q = (q + [""] * config.TOTAL_COLS)
            product = " / ".join(x for x in (
                q[config.COL_FABRIC].strip(), q[config.COL_PRODUCT_TYPE].strip(),
                q[config.COL_VARIANT].strip()) if x)
        except Exception:
            pass
        out.append({
            "lane": "images", "when": cell(config.GS_COL_POST_DATE) or cell(config.GS_COL_GEN_DATE),
            "about": f"row #{num}" + (f" ({product})" if product else ""),
            "choices": cell(config.GS_COL_POST_STATUS),
            "rating": None, "note": note, "ref": cell(config.GS_COL_POST_URL),
        })
    return out


def _edu_feedback():
    """Educational Generation Status col O 'User' + Post Topic col M remarks."""
    out = []
    try:
        import sys
        edu_dir = os.path.normpath(os.path.join(
            reel_config.BASE_DIR, "..", "selene-dreams-educational-v1.0"))
        if edu_dir not in sys.path:
            sys.path.insert(0, edu_dir)
        import config_edu as C
        vals = _sheet_values(C.EDU_QUEUE_SHEET_ID, C.TAB_STATUS)
        for r in vals[3:]:
            r = (r + [""] * 16)[:16]
            note, num, topic = r[14].strip(), r[1].strip(), r[2].strip()
            if not note:
                continue
            out.append({
                "lane": "educational", "when": r[12].strip() or r[11].strip(),
                "about": f"post #{num}, topic #{topic}", "choices": r[10].strip(),
                "rating": None, "note": note, "ref": "",
            })
    except Exception as e:
        log(f"edu sheet unavailable ({type(e).__name__})")
    return out


def _posted_feedback():
    """Every rating/note on the Posted Content sheet, all lanes, plus every
    Taste Notes row regardless of scope."""
    out = []
    try:
        import posted_sheet
        for r in posted_sheet.read_feedback() or []:
            out.append({
                "lane": r.get("lane", "manual"), "when": r.get("when", ""),
                "about": r.get("what", "") or r.get("key", ""),
                "choices": r.get("choices", ""), "rating": r.get("rating"),
                "note": r.get("note", ""), "ref": r.get("key", ""),
            })
        rows, _ = posted_sheet.read_taste_rows()
        for t in rows or []:
            out.append({
                "lane": t.get("scope", "all"), "when": t.get("date", ""),
                "about": "standing direction", "choices": "",
                "rating": None, "note": t.get("note", ""), "ref": "Taste Notes tab",
            })
    except Exception as e:
        log(f"posted sheet unavailable ({type(e).__name__})")
    return out


def collect_feedback():
    items = _posted_feedback() + _reel_feedback() + _image_feedback() + _edu_feedback()
    # De-duplicate: same ref + same note (the posted sheet and the reel state
    # can both carry a reel note, and the reel state carries taste notes too).
    seen, uniq = set(), []
    for it in items:
        k = (it.get("ref", ""), it.get("note", ""), it.get("rating"))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(it)
    items = uniq
    items.sort(key=lambda r: r.get("when", ""), reverse=True)
    return items


def collect_outcomes():
    out = []
    try:
        import reel_runner
        import reel_metrics
        state = reel_runner.load_state()
        for rec in (state.get("videos") or {}).values():
            for run in rec.get("runs", []):
                m = {}
                try:
                    m = reel_metrics.latest(run)
                except Exception:
                    pass
                if not m:
                    continue
                label = next((lab for lab, _ in reversed(reel_config.METRIC_WINDOWS)
                              if (run.get("metrics") or {}).get(lab) is m),
                             reel_metrics.PROBE)
                out.append({
                    "lane": "reels", "posted": run.get("at", "")[:10],
                    "what": f'{rec.get("filename", "")} · hook "{run.get("hook", "")}"',
                    "choices": ", ".join(x for x in (
                        run.get("hook_pattern_id"), run.get("style"),
                        run.get("hook_mode")) if x),
                    "window": label, "views": m.get("views"), "reach": m.get("reach"),
                    "likes": m.get("likes"), "comments": m.get("comments"),
                    "shares": m.get("shares"), "saves": m.get("saved"),
                    "watch_s": (round(m["ig_reels_avg_watch_time"] / 1000, 1)
                                if m.get("ig_reels_avg_watch_time") else None),
                    "url": run.get("permalink", ""),
                })
    except Exception as e:
        log(f"reel outcomes unavailable ({type(e).__name__})")
    try:
        import post_metrics
        ps = post_metrics.load_state()
        for sc, rec in ps.get("posts", {}).items():
            label, m = post_metrics.latest(rec)
            if not m:
                continue
            out.append({
                "lane": rec.get("lane", "images"),
                "posted": (rec.get("timestamp") or rec.get("posted") or "")[:10],
                "what": rec.get("ref", sc), "choices": rec.get("media_type", ""),
                "window": label, "views": m.get("views"), "reach": m.get("reach"),
                "likes": m.get("likes"), "comments": m.get("comments"),
                "shares": m.get("shares"), "saves": m.get("saved"),
                "watch_s": None, "url": rec.get("url", ""),
            })
    except Exception as e:
        log(f"carousel outcomes unavailable ({type(e).__name__})")
    out.sort(key=lambda r: r.get("posted", ""), reverse=True)
    return out


# =============================================================================
# RENDER
# =============================================================================

def _md_references(rows):
    lines = ["# References — what Marcus and the team point at",
             f"Generated {_now()} by taste_store.py {VERSION} from Drive "
             f"'02. Reference Images'. Do not edit; add or remove images in Drive.",
             ""]
    for lane in ("style", "educational"):
        sub = [r for r in rows if r["lane"] == lane]
        lines.append(f"## {lane} ({len(sub)})")
        for r in sub:
            if r["shows"]:
                lines.append(f"- {r['name']} ({r['added'][:10]}): {r['shows']} "
                             f"On-brand: {r['on_brand']} Borrow: {r['borrow']}")
            else:
                lines.append(f"- {r['name']} ({r['added'][:10]}): (not yet described)")
        lines.append("")
    return "\n".join(lines)


def _md_feedback(rows):
    lines = ["# Feedback — Marcus's and the team's own words",
             f"Generated {_now()} by taste_store.py {VERSION}. Sources: Trial "
             f"Reel sheet (Q Notes / W Rating), Taste Notes tab, image-lane "
             f"Generation Status col N, educational Generation Status col O. "
             f"Do not edit here; edit the sheets.",
             "", "Ratings: 5 = exactly right, 1 = wrong.", ""]
    standing = [r for r in rows if r["about"] == "standing direction"]
    if standing:
        lines.append("## Standing directions")
        for r in standing:
            lines.append(f"- [{r['lane']}] {r['note']}  ({r['when']})")
        lines.append("")
    for lane in ("reels", "images", "educational", "manual"):
        sub = [r for r in rows if r["lane"] == lane and r["about"] != "standing direction"]
        lines.append(f"## {lane} ({len(sub)})")
        for r in sub:
            bits = []
            if r.get("rating") is not None:
                bits.append(f"rated {r['rating']:.0f}/5")
            if r.get("note"):
                bits.append(f'"{r["note"]}"')
            ctx = f" [{r['choices']}]" if r.get("choices") else ""
            lines.append(f"- {r['when']} · {r['about']}{ctx}: " + "; ".join(bits))
        lines.append("")
    return "\n".join(lines)


def _md_outcomes(rows):
    lines = ["# Outcomes — what the audience actually did",
             f"Generated {_now()} by taste_store.py {VERSION} from reel_metrics "
             f"and post_metrics. Windows are fixed ages (72h, 7d) so numbers "
             f"are comparable across posts and lanes. Never edit.",
             "", "| lane | posted | what | choices | window | views | reach | likes | comments | shares | saves | watch s |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        v = lambda k: "" if r.get(k) is None else r[k]
        lines.append(f"| {r['lane']} | {r['posted']} | {r['what']} | {r['choices']} | "
                     f"{r['window']} | {v('views')} | {v('reach')} | {v('likes')} | "
                     f"{v('comments')} | {v('shares')} | {v('saves')} | {v('watch_s')} |")
    lines.append("")
    return "\n".join(lines)


# =============================================================================
# SYNC
# =============================================================================

def write_local(dest_dir):
    """Write the three files (+ json) into dest_dir/taste. Returns paths."""
    tdir = os.path.join(dest_dir, TASTE_DIR)
    os.makedirs(tdir, exist_ok=True)
    refs, fb, outs = collect_references(), collect_feedback(), collect_outcomes()
    files = {
        "references.md": _md_references(refs), "references.json": json.dumps(refs, indent=1),
        "feedback.md": _md_feedback(fb), "feedback.json": json.dumps(fb, indent=1),
        "outcomes.md": _md_outcomes(outs), "outcomes.json": json.dumps(outs, indent=1),
    }
    for name, body in files.items():
        with open(os.path.join(tdir, name), "w") as f:
            f.write(body)
    log(f"taste/: {len(refs)} reference(s), {len(fb)} feedback item(s), "
        f"{len(outs)} outcome(s)")
    return tdir


def sync():
    """Clone the memory repo, regenerate taste/, push. Never raises.
    Returns (ok, message)."""
    workdir = tempfile.mkdtemp(prefix="selene_taste_")
    try:
        from caption_runner import clone_memory
        import pipeline_state
        mem = clone_memory(workdir)
        if not mem:
            return False, "memory repo clone failed"
        write_local(mem)
        try:
            import taste_brief
            taste_brief.refresh_cache_from(mem)
        except Exception:
            pass
        ok, msg = pipeline_state.push_with_retry(
            mem, f"Taste layer {datetime.now():%Y-%m-%d %H:%M}", logger=log)
        _stamp()
        return ok, msg
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:120]}"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _stamp():
    try:
        os.makedirs(os.path.dirname(STAMP_PATH), exist_ok=True)
        with open(STAMP_PATH, "w") as f:
            f.write(_now())
    except Exception:
        pass


def due():
    try:
        age = time.time() - os.path.getmtime(STAMP_PATH)
        return age >= SYNC_EVERY_HOURS * 3600
    except Exception:
        return True


def maybe_sync():
    """Called from the reel tick. Syncs at most every SYNC_EVERY_HOURS."""
    if not due():
        return False, "not due"
    ok, msg = sync()
    log(f"sync: {msg}" if ok else f"WARNING: sync failed ({msg})")
    return ok, msg


if __name__ == "__main__":
    import sys
    if "--sync" in sys.argv:
        ok, msg = sync()
        print(("synced: " if ok else "FAILED: ") + msg)
    elif "--local" in sys.argv:
        d = write_local(os.path.join(reel_config.BASE_DIR, "_state", "taste-preview"))
        print(f"written to {d}")
    else:
        print(f"taste_store {VERSION}. --sync (clone, regenerate taste/, push) "
              f"or --local (write a preview under _state/taste-preview)")
