# =============================================================================
# brief_edu.py — a hidden VISUAL BRIEF per slide, for matching and generation
# VERSION 1.0 — 2026-09-10
# CHANGELOG
#   1.0  2026-09-10  First release. Marcus's matching design (2026-09-10): the
#                    words on a slide are too thin to find a picture by ("Put The
#                    Phone Down First" contains no visual noun), so each slide
#                    gets a brief of what the photograph should show. It lives in
#                    the Post Topic sheet, columns N-T (Brief 1..7), hidden, and
#                    is never displayed. The picker matches it against library
#                    descriptions; when nothing matches it is the GEN prompt seed.
#                    Runs for any Approved topic that has slide copy (written by
#                    the writer or by Marcus) and no briefs yet. One Claude call
#                    per topic. Photo-essay types get a brief per IMAGE slot, not
#                    per text cell, so wordless slides are briefed too.
# =============================================================================
import os, re, tempfile, shutil
import config_edu as C
import sheets_edu as S
from templates_edu import DEFAULT_PLANS, SERIES_FOR, NO_TEXT_TEMPLATES
from log_edu import log
from claude_client import invoke_claude_json

BRIEF_SCHEMA = {"briefs": {"type": "list", "required": True, "min_len": 1}}
BRIEF_COLS = "N:T"          # Post Topic sheet: Brief 1..7
MAX_BRIEFS = 7


def _prompt():
    path = os.path.join(C.PROMPT_DIR, "brief_edu.md")
    with open(path) as f:
        text = f.read()
    m = re.search(r"<!--\s*VERSION:\s*([^\s>]+)\s*-->", text)
    return text, (m.group(1) if m else "unversioned")


def slide_slots(topic):
    """The image slots this post will render, in order, each with its words or
    (photo only). Mirrors plan_edu._fit_plan without importing the planner."""
    plan = [t for t in DEFAULT_PLANS.get(topic["type"], DEFAULT_PLANS["Fabric Education"])
            if t != "outro"]
    texts = [s for s in topic["slides"] if s.strip()]
    out, used = [], 0
    for t in plan:
        if t in NO_TEXT_TEMPLATES:
            out.append("")
        elif used < len(texts):
            out.append(texts[used]); used += 1
        else:
            break
    return out[:C.MAX_SLIDES]


def brief_topic(topic):
    """Returns (ok, briefs_or_error)."""
    slots = slide_slots(topic)
    if not slots:
        return False, "no slides"
    block = "\n".join(
        f"  slide {i}: {s.strip() if s.strip() else '(photo only)'}"
        for i, s in enumerate(slots, 1))
    tpl, ver = _prompt()
    workdir = tempfile.mkdtemp(prefix=f"selene_brief_{topic['num']}_")
    try:
        out_path = os.path.join(workdir, "briefs.json")
        prompt = tpl.format(topic_type=topic["type"],
                            series=SERIES_FOR.get(topic["type"], topic["type"]),
                            topic_desc=topic["desc"] or "(no description given)",
                            n_slides=len(slots), slides_block=block, out_path=out_path)
        log(f"  brief #{topic['num']}: invoking Claude ({ver}) for {len(slots)} slide(s)")
        ok, res = invoke_claude_json(prompt, workdir, out_path, schema=BRIEF_SCHEMA,
                                     stage="brief_edu", timeout=C.WRITER_TIMEOUT)
        if not ok:
            return False, res
        got = {int(b.get("n", 0)): str(b.get("brief", "")).strip() for b in res.get("briefs", [])}
        briefs = [got.get(i, "") for i in range(1, len(slots) + 1)]
        if any(not b for b in briefs):
            return False, f"missing brief(s): {[i+1 for i, b in enumerate(briefs) if not b]}"
        return True, briefs
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def needs_brief(t):
    has_text = any(s.strip() for s in t["slides"])
    has_brief = any(b.strip() for b in t.get("briefs", []))
    return (t["status"] == "Approved" and t["type"] not in C.PARKED_TYPES
            and has_text and not has_brief)


def run(limit=None):
    ws = S.topic_sheet().worksheet(C.TAB_TOPICS)
    done = failed = 0
    for t in S.topics_rows():
        if not needs_brief(t):
            continue
        ok, res = brief_topic(t)
        if ok:
            cells = (res + [""] * MAX_BRIEFS)[:MAX_BRIEFS]
            a, b = BRIEF_COLS.split(":")
            ws.update(values=[cells], range_name=f"{a}{t['row']}:{b}{t['row']}")
            done += 1
            log(f"  brief #{t['num']}: {len(res)} brief(s) written")
        else:
            failed += 1
            log(f"  brief #{t['num']} ERROR: {res}")
        if limit and done + failed >= limit:
            break
    return f"{done} briefed, {failed} failed"


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    print(run(limit=lim))
