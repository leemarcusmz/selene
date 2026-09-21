#!/usr/bin/env python3
"""
hub_sync.py  v1.3  (2026-09-21)
Parses the weekly IG research archive into one JSON payload for the
Selene Flow Hub artifact. Run it, then feed hub-data.json into the
artifact's database.

Usage:  python3 hub_sync.py [--out PATH]
Default out: ~/Desktop/_Claude Cowork/_00. Memory/_hub_sync/hub-data.json

CHANGELOG
  v1.3  2026-09-21  COMMENT INTENT parser now also handles the compact
                    "brand (n=40, 3 posts): CLASS N, CLASS N" header format
                    introduced by the 2026-09-21 run (post count moved inside
                    the parenthesis and the word "comments" dropped, so the
                    v1.1/v1.2 header regex matched nothing and the week parsed
                    0 brands). Header matching is now count-then-anything up to
                    the closing parenthesis, and the inline class tail is taken
                    from after that parenthesis instead of the first colon on
                    the line (which previously mis-split headers that carry a
                    "3 posts: <shortcodes>" list inside the parenthesis).
  v1.2  2026-09-14  FIELD ORDER CORRECTED. The STATS line is
                    account | followers | FOLLOWS | MEDIA — not
                    followers|media|follows as v1.0/v1.1 assumed. Confirmed
                    against the Instagram Graph API for selenedreams_official
                    (followers 19,906 / follows 5,832 / media 82 vs the scrape's
                    19,908 | 5,831 | 81). The mislabelling made the account look
                    like it had 5,831 posts when it has 82, and propagated into
                    the Flow Diagnostic. Fields are now named `follows` and
                    `media`; `posts` is kept as an alias of `media` so older
                    documents still render.
  v1.1  2026-09-14  COMMENT INTENT parser now also handles the
                    "n=45 comments" header and "KEY=22" pair format
                    (2026-08-31 run parsed 0 brands before this).
  v1.0  2026-09-14  first version. Handles the three COMMENT INTENT
                    formats found across runs 2026-08-10 .. 2026-09-14.
"""
import os, re, json, glob, argparse, datetime

RESEARCH = os.path.expanduser(
    "~/Desktop/_Claud/Work Projects/Selene Dreams/AI Generation Flow/"
    "selene-dreams-script-v3.0/_research")
FALLBACK = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "selene-dreams-script-v3.0", "_research")
VERSION = "1.3"

def num(x):
    try: return int(x)
    except Exception: return None

def parse_intent(block):
    """Handles five observed formats: inline-comma, bullet-list,
    pipe-separated, the "n=N comments" / "KEY=N" variant, and the compact
    "brand (n=N, P posts): CLASS N, CLASS N" header (2026-09-21 onwards)."""
    out, cur = {}, None
    for raw in block.split("\n"):
        line = raw.strip()
        if not line: continue
        m = re.match(r"^([a-z0-9_.]+)\s*\((?:n=)?(\d+)(?=[\s,)])[^)]*\)\s*:", line)
        if m:
            cur = m.group(1)
            out.setdefault(cur, {"_total": int(m.group(2))})
            tail = line[m.end():]
            for seg in re.split(r"[,|]", tail):
                mm = re.match(r"^\s*([A-Z][A-Z\- ]+?)\s*[:= ]\s*(\d+)", seg.strip())
                if mm: out[cur][mm.group(1).strip()] = int(mm.group(2))
            continue
        if cur:
            pairs = re.findall(r"\b([A-Z][A-Z\-]+(?:[ ][A-Z][A-Z\-]+)*)\s*[:=]\s*(\d+)", line)
            if pairs:
                for k, v in pairs: out[cur][k.strip()] = int(v)
                continue
            if "|" in line and re.search(r"[A-Z] \d", line):
                for seg in line.split("|"):
                    s = seg.strip().rsplit(" ", 1)
                    if len(s) == 2 and s[1].isdigit():
                        out[cur][s[0].strip()] = int(s[1])
                continue
            if not line.startswith(("-", "No ", "DATA")): cur = None
    return {k: v for k, v in out.items() if len(v) > 1}

def section(txt, name):
    m = re.search(r"##\s*" + name + r"(.*?)(?=\n##\s|\Z)", txt, re.S)
    return m.group(1) if m else ""

def parse_week(d, root):
    w = {"date": d, "stats": [], "posts": [], "captions": [],
         "intent": {}, "objections": [], "intentNote": "", "purchase": []}
    p1 = os.path.join(root, d, "step1-raw.md")
    if os.path.exists(p1):
        sec = None
        for line in open(p1, errors="replace"):
            line = line.rstrip()
            if line.startswith("## "):
                sec = line[3:].split("(")[0].strip(); continue
            if "|" not in line: continue
            f = [x.strip() for x in line.split("|")]
            if sec == "STATS" and len(f) >= 4:
                follows, media = num(f[2]), num(f[3])
                w["stats"].append({"a": f[0], "fol": num(f[1]),
                                   "follows": follows, "media": media,
                                   "posts": media})
            elif sec == "POSTS" and len(f) >= 7:
                w["posts"].append({"a": f[0], "t": f[1], "l": num(f[2]),
                                   "c": num(f[3]), "v": num(f[4]),
                                   "d": f[5][:10], "u": f[6]})
    p2 = os.path.join(root, d, "step2-captions-comments.md")
    if os.path.exists(p2):
        txt = open(p2, errors="replace").read()
        for line in section(txt, "CAPTIONS").split("\n"):
            if "instagram.com" not in line: continue
            parts = [x.strip() for x in line.split(" | ")]
            url = next((x for x in parts if "instagram.com" in x), None)
            acct = parts[0] if parts and not parts[0].startswith("http") else None
            cap = parts[-1] if len(parts) > 1 and "instagram.com" not in parts[-1] else ""
            if url and cap:
                w["captions"].append({"u": url, "a": acct, "c": cap[:700]})
        ib = section(txt, "COMMENT INTENT")
        w["intent"] = parse_intent(ib)
        fl = re.search(r"(DATA QUALITY FLAG.*?)(?:\n\n|\Z)", ib + txt, re.S)
        if fl: w["intentNote"] = re.sub(r"\s+", " ", fl.group(1))[:700]
        for label, key in (("OBJECTIONS \\(verbatim\\)", "objections"),
                           ("PURCHASE INTENT \\(verbatim\\)", "purchase")):
            for line in section(txt, label).split("\n"):
                mm = re.match(r"^\d+\.\s*([a-z0-9_.]+)\s*\|\s*(.+)$", line.strip())
                if mm: w[key].append({"a": mm.group(1), "t": mm.group(2)[:500]})
    return w

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.expanduser(
        "~/Desktop/_Claude Cowork/_00. Memory/_hub_sync/hub-data.json"))
    a = ap.parse_args()
    root = RESEARCH if os.path.isdir(RESEARCH) else FALLBACK
    weeks = [d for d in sorted(os.listdir(root))
             if re.match(r"^\d{4}-\d{2}-\d{2}$", d)]
    payload = {"version": VERSION,
               "generatedAt": datetime.datetime.now().isoformat(timespec="seconds"),
               "researchRoot": root,
               "weeks": [parse_week(d, root) for d in weeks]}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(payload, open(a.out, "w"))
    for w in payload["weeks"]:
        print(f"{w['date']}  stats {len(w['stats'])}  posts {len(w['posts'])}"
              f"  caps {len(w['captions'])}  intent {len(w['intent'])}"
              f"  obj {len(w['objections'])}  buy {len(w['purchase'])}")
    print("->", a.out, os.path.getsize(a.out), "bytes")

if __name__ == "__main__":
    main()
