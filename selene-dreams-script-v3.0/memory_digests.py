# =============================================================================
# Selene Dreams — Memory Digests v1.0 (2026-08-12)
# memory_digests.py — Make the agents READ what the pipeline has been writing
# =============================================================================
#
# THE GAP THIS CLOSES: the pipeline had been diligently recording evidence
# that nothing ever read back.
#
#   - prompt-playbook.md held every prompt and the score it earned, but the
#     prompt writer never opened it — so it could not prefer the phrasings
#     that worked. That was the entire point of keeping it.
#   - screening-attributes.csv accumulated the qualities of every candidate,
#     kept and cut, and no agent consumed a single row.
#   - post-outcomes.csv and generation-scores.csv recorded what actually
#     happened after publishing, and neither the weekly nor the monthly agent
#     knew the files existed.
#
# A system that writes evidence it never reads is keeping a diary, not
# learning. These digests are the reading half.
#
# DESIGN RULE: every digest is COMPACT and SELF-LIMITING. These get injected
# into prompts, so an unbounded dump would crowd out the actual task and grow
# without limit as the files do. Each returns a short, plain-text brief, and
# says honestly when there is not yet enough data to conclude anything —
# which matters, because a confident-sounding digest built on four rows would
# teach the agents noise.
# =============================================================================

import csv
import os
import re
from collections import defaultdict

PLAYBOOK_FILE = "prompt-playbook.md"
ATTR_CSV = "screening-attributes.csv"
SCORES_CSV = "generation-scores.csv"
OUTCOMES_CSV = "post-outcomes.csv"
SELECTIONS_FILE = "selections.md"

ROW_RE = re.compile(r"^### ROW (\d+)\s*·\s*(\S+)\s*·\s*(.*)$")
QA_RE = re.compile(r"^- QA: avg ([\d.]+)/12\s*·\s*verdict (\w+)")
LEARN_RE = re.compile(r"^- PROMPT LEARNING:\s*(.+)$")
IMG_RE = re.compile(r"^\s+- img (\d+): ([\d.]+)/12\s*·\s*fidelity (\w+)")
URL_RE = re.compile(r"https?://\S+?(?=[,\s]|$)")

ATTRIBUTES = ["setting", "timeOfDay", "palette", "humanPresence", "crop",
              "textOverlay", "styling"]


def _read(path):
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return ""


def _rows(path):
    try:
        with open(path) as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


# =============================================================================
# 1. PROMPT PLAYBOOK → the prompt writer
# =============================================================================

def parse_playbook(mem_dir):
    """[{row, date, product, qaAvg, verdict, learning, drift}] newest last."""
    text = _read(os.path.join(mem_dir or "", PLAYBOOK_FILE))
    if not text:
        return []
    entries, cur = [], None
    for line in text.split("\n"):
        m = ROW_RE.match(line)
        if m:
            if cur:
                entries.append(cur)
            cur = {"row": int(m.group(1)), "date": m.group(2),
                   "product": m.group(3).strip(), "qaAvg": None,
                   "verdict": None, "learning": None, "drift": 0}
            continue
        if not cur:
            continue
        q = QA_RE.match(line)
        if q:
            cur["qaAvg"] = float(q.group(1))
            cur["verdict"] = q.group(2)
            continue
        l = LEARN_RE.match(line)
        if l:
            cur["learning"] = l.group(1).strip()
            continue
        i = IMG_RE.match(line)
        if i and i.group(3).lower().startswith("off"):
            cur["drift"] += 1
    if cur:
        entries.append(cur)
    return entries


def playbook_digest(mem_dir, limit=8):
    """What past prompts produced — so the writer can repeat what worked."""
    entries = parse_playbook(mem_dir)
    scored = [e for e in entries if e["qaAvg"] is not None]
    if not scored:
        pending = len(entries)
        return ("No scored prompts yet"
                + (f" ({pending} awaiting QA)" if pending else "")
                + " — this is the first generation of the playbook. Write "
                  "carefully; your prompts become the reference for later runs.")

    recent = scored[-limit:][::-1]
    best = max(scored, key=lambda e: e["qaAvg"])
    worst = min(scored, key=lambda e: e["qaAvg"])

    out = [f"PROMPT PLAYBOOK — {len(scored)} scored prompt set(s) so far. "
           f"What they produced, newest first:"]
    for e in recent:
        bits = [f"- ROW {e['row']} ({e['product']}): {e['qaAvg']:.1f}/12"]
        if e["verdict"]:
            bits.append(e["verdict"])
        if e["drift"]:
            bits.append(f"PRODUCT DRIFT on {e['drift']} image(s)")
        out.append(" · ".join(bits))
        if e["learning"]:
            out.append(f"    learning: {e['learning']}")

    out.append("")
    out.append(f"Best so far: ROW {best['row']} at {best['qaAvg']:.1f}/12. "
               f"Weakest: ROW {worst['row']} at {worst['qaAvg']:.1f}/12.")
    out.append("USE THIS: reuse the phrasing patterns from sets that scored "
               ">=8; avoid the shapes of anything <=6 or flagged for product "
               "drift. Where a learning names a specific phrase, treat it as "
               "an instruction, not a suggestion.")
    if len(scored) < 4:
        out.append("CAUTION: fewer than 4 scored sets — treat these as weak "
                   "signals, not rules.")
    return "\n".join(out)


# =============================================================================
# 2. SCREENING ATTRIBUTES → the screener
# =============================================================================

def picked_urls(mem_dir):
    """Post URLs a human actually picked, from selections.md."""
    text = _read(os.path.join(mem_dir or "", SELECTIONS_FILE))
    urls = set()
    for line in text.split("\n"):
        if "PICKED by" in line:
            urls.update(u.rstrip(".,") for u in URL_RE.findall(line))
    return urls


def attribute_digest(mem_dir, min_rows=20, min_group=3):
    """Which creative attributes correlate with a high score, and — the
    non-circular signal — with a human actually picking the reference."""
    rows = _rows(os.path.join(mem_dir or "", ATTR_CSV))
    if len(rows) < min_rows:
        return (f"Attribute history: only {len(rows)} candidate(s) tagged so "
                f"far (need {min_rows}+ before patterns mean anything). Score "
                f"on the rubric alone for now.")

    picked = picked_urls(mem_dir)
    stats = defaultdict(lambda: {"n": 0, "score": 0.0, "kept": 0, "picked": 0,
                                 "hasUrl": 0})
    for r in rows:
        try:
            score = float(r.get("score") or 0)
        except ValueError:
            continue
        url = (r.get("postUrl") or "").strip()
        for attr in ATTRIBUTES:
            val = (r.get(attr) or "").strip()
            if not val:
                continue
            s = stats[(attr, val)]
            s["n"] += 1
            s["score"] += score
            s["kept"] += 1 if (r.get("kept") or "").lower() == "yes" else 0
            if url:
                s["hasUrl"] += 1
                s["picked"] += 1 if url in picked else 0

    out = [f"ATTRIBUTE HISTORY — {len(rows)} candidates tagged across past "
           f"weeks. Mean rubric score by attribute value "
           f"(groups of {min_group}+ only):"]
    for attr in ATTRIBUTES:
        vals = [(v, s) for (a, v), s in stats.items()
                if a == attr and s["n"] >= min_group]
        if not vals:
            continue
        vals.sort(key=lambda kv: -(kv[1]["score"] / kv[1]["n"]))
        parts = []
        for v, s in vals[:4]:
            mean = s["score"] / s["n"]
            bit = f"{v} {mean:.1f} (n={s['n']})"
            if s["hasUrl"] >= min_group:
                bit += f" picked {s['picked']}/{s['hasUrl']}"
            parts.append(bit)
        out.append(f"- {attr}: " + " · ".join(parts))

    out.append("")
    out.append("USE THIS AS CONTEXT, NOT AS A SHORTCUT: brand-guide.md still "
               "decides. Where these numbers and the rubric disagree, the "
               "rubric wins — the numbers describe what has been seen, the "
               "rubric describes what the brand is. Where 'picked' counts "
               "exist they are the stronger signal, because they come from a "
               "human rather than from your own past scores.")
    return "\n".join(out)


# =============================================================================
# 3. OUTCOMES → everybody
# =============================================================================

def outcomes_digest(mem_dir, limit=6):
    """What actually happened after publishing."""
    rows = [r for r in _rows(os.path.join(mem_dir or "", OUTCOMES_CSV))
            if (r.get("likes") or "").strip() or (r.get("comments") or "").strip()]
    if not rows:
        return ("No published-post outcomes recorded yet — paste live post "
                "URLs into Generation Status column O and this fills in.")

    def eng(r):
        try:
            return int(float(r.get("likes") or 0)) + \
                   int(float(r.get("comments") or 0))
        except ValueError:
            return 0

    ranked = sorted(rows, key=eng, reverse=True)
    out = [f"PUBLISHED OUTCOMES — {len(rows)} post(s) matched to the rows that "
           f"made them. Best performing first:"]
    for r in ranked[:limit]:
        qa = (r.get("qaAvgScore") or "").strip()
        out.append(
            f"- row {r.get('row')} · {r.get('fabric','')} "
            f"{r.get('productType','')} {r.get('variant','')} · "
            f"{eng(r)} interactions"
            + (f" · QA {qa}/12" if qa else "")
            + (f" · {r.get('postDate')}" if r.get("postDate") else ""))

    # Only draw a QA-vs-performance comparison when there is enough to compare.
    with_qa = [(float(r["qaAvgScore"]), eng(r)) for r in rows
               if (r.get("qaAvgScore") or "").strip()]
    if len(with_qa) >= 6:
        with_qa.sort()
        half = len(with_qa) // 2
        low = sum(e for _, e in with_qa[:half]) / half
        high = sum(e for _, e in with_qa[-half:]) / half
        out.append("")
        out.append(f"Higher-QA posts average {high:.0f} interactions vs "
                   f"{low:.0f} for lower-QA posts "
                   f"({'the rubric is tracking performance' if high > low else 'the rubric is NOT tracking performance — worth questioning'}).")
    elif len(with_qa) >= 1:
        out.append("")
        out.append(f"Only {len(with_qa)} post(s) have both a QA score and "
                   f"metrics — too few to say whether the rubric predicts "
                   f"performance.")
    return "\n".join(out)


def generation_quality_digest(mem_dir, min_rows=6):
    """How the pipeline's own output has been scoring lately."""
    rows = _rows(os.path.join(mem_dir or "", SCORES_CSV))
    if len(rows) < min_rows:
        return (f"Generation quality: only {len(rows)} scored image(s) so far "
                f"— not enough to characterise.")
    scores, drift = [], 0
    by_fabric = defaultdict(list)
    for r in rows:
        try:
            s = float(r.get("score") or 0)
        except ValueError:
            continue
        scores.append(s)
        by_fabric[(r.get("fabric") or "?").strip()].append(s)
        if (r.get("fidelity") or "").lower().startswith("off"):
            drift += 1
    if not scores:
        return "Generation quality: no usable scores recorded."
    mean = sum(scores) / len(scores)
    worst = sorted(by_fabric.items(),
                   key=lambda kv: sum(kv[1]) / len(kv[1]))[:2]
    out = [f"GENERATION QUALITY — {len(scores)} generated image(s) scored, "
           f"mean {mean:.1f}/12, product drift on {drift} "
           f"({drift / len(scores):.0%})."]
    if worst:
        out.append("Weakest fabrics: " + " · ".join(
            f"{f} {sum(v)/len(v):.1f}/12 (n={len(v)})" for f, v in worst))
    return "\n".join(out)
