# =============================================================================
# Selene Dreams — Research Pool Hygiene v1.0 (2026-09-30)
# research_pool.py — the deterministic half of research lane v2.1
# =============================================================================
#
# WHY THIS EXISTS. The 30 Sep 2026 diagnosis of shortlists 24 Aug-28 Sep:
#   - posts already OFFERED came back (28 Sep: 5 of 8 were repeats — four of
#     them via the screener's top-up, one via phase 4 itself);
#   - posts Marcus already PICKED came back and were picked again
#     (DcCN9qWj7Gy 4x, Db8DEjuirpr 3x) because selections.md's dedup only
#     retired a post after it was PASSED twice;
#   - the same 4-5 accounts every week (sijohome, coyuchi, kottonkaustralia,
#     parachutehome).
# A prompt rule alone cannot fix that: the agent reads selections.md and
# applies whatever model it infers. This module makes the rule CODE:
#
#   history(mem, week)   -> everything ever offered or picked BEFORE `week`,
#                           and when each account was last offered
#   enforce(entries, …)  -> drop excluded posts, cap 2 per account, tag each
#                           entry with `account` and `freshAccount`
#   *_block(…)           -> the prompt text phase 4 receives
#
# "Offered" = appeared in ANY candidates-*.json or shortlist-*.json (the pool
# is what selections.md itself calls "offered"). "Picked" = every URL on a
# "PICKED by" line in selections.md. A post is excluded forever once it has
# been either. "Fresh account" = not offered in the FRESH_WEEKS weeks before
# `week`; the screener reserves FRESH_SLOTS of its shortlist for them.
#
# Used by research_runner.py (build the exclusion, enforce after phase 4) and
# screen_runner.py (reserve the fresh slots, cap per account). Pure functions,
# no network, no secrets.
# =============================================================================
# CHANGELOG
#   1.0  2026-09-30  First build (research lane v2.1).
# =============================================================================

import glob
import json
import os
import re
from datetime import date, timedelta

VERSION = "1.0"

ACCOUNT_CAP = 2        # posts per account in one week's pool / shortlist
FRESH_WEEKS = 4        # "not offered in the last 4 weeks"
FRESH_SLOTS = 3        # of the shortlist, reserved for fresh accounts
FRESH_POOL_MIN = 8     # phase 4 is asked for at least this many fresh-account
                       # candidates so the screener can actually fill 3 slots

_SC = re.compile(r"instagram\.com/(?:p|reel|reels)/([A-Za-z0-9_-]+)")
_HANDLE = re.compile(r"@([A-Za-z0-9_.]+)")
_WEEK = re.compile(r"(\d{4}-\d{2}-\d{2})")
_PICKED = re.compile(r"^\s*-\s*PICKED\b.*$", re.M)


def shortcode(url):
    """'https://www.instagram.com/p/DcCN9qWj7Gy/' -> 'DcCN9qWj7Gy'.
    Falls back to the stripped URL so an odd URL still dedups against itself."""
    if not url:
        return ""
    m = _SC.search(url)
    return m.group(1) if m else url.strip().rstrip("/")


def account_of(entry):
    """The account an entry came from, as '@handle', lower-cased.

    Order: an explicit `account` field (phase 4 writes it from v2.1 on) ->
    a handle inside `source` ('#linenbedding (@kottonkaustralia)') -> the
    first handle in `concept` ('@collectiveinteriors — …') -> the source
    itself (a bare hashtag, the best key available for older files)."""
    for key in ("account", "source", "concept"):
        v = entry.get(key) or ""
        m = _HANDLE.search(v)
        if m:
            return "@" + m.group(1).lower().rstrip(".")
    src = (entry.get("source") or "").strip().lower()
    return src or "?"


def _week_of(path):
    m = _WEEK.search(os.path.basename(path))
    return m.group(1) if m else None


def _load_entries(path):
    try:
        with open(path) as f:
            d = json.load(f)
        return d.get("entries") or []
    except Exception:
        return []


def history(mem, week):
    """Everything the lane has already shown, strictly BEFORE `week`.

    Returns a dict:
      offered        {shortcode: first week offered}
      picked         {shortcode}   (all weeks, including `week` itself —
                                    a pick is a pick)
      last_offered   {account: latest week that account was offered}
      recent_accounts  set of accounts offered in the FRESH_WEEKS before week
      weeks          sorted list of the weeks that were read
    """
    offered, last_offered, weeks = {}, {}, set()
    for sub in ("candidates", "shortlists"):
        for path in sorted(glob.glob(os.path.join(mem, sub, "*.json"))):
            wk = _week_of(path)
            if not wk or wk >= week:
                continue
            weeks.add(wk)
            for e in _load_entries(path):
                sc = shortcode(e.get("postUrl"))
                if sc:
                    offered.setdefault(sc, wk)
                acct = account_of(e)
                if acct and acct != "?":
                    if wk > last_offered.get(acct, ""):
                        last_offered[acct] = wk

    picked = set()
    sel = os.path.join(mem, "selections.md")
    if os.path.exists(sel):
        with open(sel, encoding="utf-8", errors="replace") as f:
            text = f.read()
        for line in _PICKED.findall(text):
            for m in _SC.finditer(line):
                picked.add(m.group(1))

    cutoff = fresh_cutoff(week)
    recent = {a for a, wk in last_offered.items() if wk >= cutoff}
    return {"offered": offered, "picked": picked, "last_offered": last_offered,
            "recent_accounts": recent, "weeks": sorted(weeks)}


def fresh_cutoff(week):
    """Accounts offered on/after this Monday are NOT fresh for `week`."""
    y, m, d = (int(x) for x in week.split("-"))
    return (date(y, m, d) - timedelta(weeks=FRESH_WEEKS)).isoformat()


def is_fresh(entry, hist):
    return account_of(entry) not in hist["recent_accounts"]


def enforce(entries, hist, cap=ACCOUNT_CAP, renumber=True):
    """Apply the rules to a candidate pool IN ORDER (order = the agent's
    ranking, so the cap keeps its top picks per account).

    Returns (kept_entries, report). Every kept entry gains `account` and
    `freshAccount`; `n` is renumbered 1..N unless renumber=False (the screener
    keeps the original n — the origN invariant: archived images are named by
    the candidates file's own numbering). `report` is a dict of what was
    dropped and why — log it, and put it in the data notes."""
    kept, seen_sc, per_acct = [], set(), {}
    dropped = {"offered": [], "picked": [], "duplicate": [], "account_cap": []}
    for e in entries:
        sc = shortcode(e.get("postUrl"))
        acct = account_of(e)
        tag = f"{acct} {sc}"
        if sc in hist["picked"]:
            dropped["picked"].append(tag)
            continue
        if sc in hist["offered"]:
            dropped["offered"].append(f"{tag} (first {hist['offered'][sc]})")
            continue
        if sc in seen_sc:
            dropped["duplicate"].append(tag)
            continue
        if per_acct.get(acct, 0) >= cap:
            dropped["account_cap"].append(tag)
            continue
        seen_sc.add(sc)
        per_acct[acct] = per_acct.get(acct, 0) + 1
        ne = dict(e)
        ne["account"] = acct
        ne["freshAccount"] = acct not in hist["recent_accounts"]
        kept.append(ne)
    if renumber:
        for i, e in enumerate(kept, 1):
            e["n"] = i
    fresh_n = sum(1 for e in kept if e["freshAccount"])
    report = {"kept": len(kept), "fresh_accounts": fresh_n,
              "accounts": per_acct, "dropped": dropped}
    return kept, report


def report_lines(report):
    d = report["dropped"]
    out = [f"pool kept {report['kept']} · {report['fresh_accounts']} from "
           f"fresh accounts · per account: "
           + ", ".join(f"{a} {n}" for a, n in sorted(report["accounts"].items()))]
    for k, label in (("picked", "already PICKED"), ("offered", "already offered"),
                     ("duplicate", "duplicate in pool"),
                     ("account_cap", f"over the {ACCOUNT_CAP}-per-account cap")):
        if d[k]:
            out.append(f"dropped {len(d[k])} {label}: " + "; ".join(d[k]))
    return out


# ---- prompt blocks ---------------------------------------------------------

def exclude_block(hist):
    """The hard-exclude list phase 4 receives. Shortcodes only — short enough
    to paste in full, unambiguous to match against a postUrl."""
    ex = sorted(set(hist["offered"]) | hist["picked"])
    picked = sorted(hist["picked"])
    lines = [
        f"HARD EXCLUDE — {len(ex)} posts already offered or picked in "
        f"{len(hist['weeks'])} earlier weeks. A post whose URL contains any of "
        f"these shortcodes must NOT enter the pool, whatever its engagement or "
        f"fit. The runner re-checks this after you finish and deletes "
        f"offenders, so listing one only wastes a slot.",
        "",
        " ".join(ex) if ex else "(nothing yet)",
        "",
        f"Of those, {len(picked)} were PICKED by the team and have already "
        f"become Selene posts: " + (" ".join(picked) if picked else "(none)"),
    ]
    return "\n".join(lines)


def accounts_block(hist, week):
    """Which accounts count as fresh this week, and which do not."""
    cutoff = fresh_cutoff(week)
    recent = sorted(hist["recent_accounts"])
    older = sorted(a for a in hist["last_offered"] if a not in hist["recent_accounts"])
    return "\n".join([
        f"ACCOUNT ROTATION — offered in the last {FRESH_WEEKS} weeks "
        f"(since {cutoff}), so NOT fresh: " + (", ".join(recent) or "(none)"),
        f"Offered before that and fresh again: " + (", ".join(older) or "(none)"),
        f"Never offered = fresh. Cap: {ACCOUNT_CAP} posts per account. "
        f"Target: at least {FRESH_POOL_MIN} candidates from fresh accounts so "
        f"the screener can fill its {FRESH_SLOTS} reserved fresh slots.",
    ])


def select_shortlist(scored, hist, smin, smax, cap=ACCOUNT_CAP,
                     fresh_slots=FRESH_SLOTS):
    """Screener-side selection. `scored` = kept candidates sorted best-first.

    1. cap per account; 2. reserve `fresh_slots` for fresh-account entries
    (best-first) when at least that many passed; 3. fill the rest best-first
    up to smax. Returns (chosen, note)."""
    per_acct, chosen, ids = {}, [], set()

    def take(e):
        acct = account_of(e)
        if per_acct.get(acct, 0) >= cap or id(e) in ids:
            return False
        per_acct[acct] = per_acct.get(acct, 0) + 1
        ids.add(id(e))
        chosen.append(e)
        return True

    fresh = [e for e in scored
             if e.get("freshAccount", account_of(e) not in hist["recent_accounts"])]
    got_fresh = 0
    for e in fresh:
        if got_fresh >= fresh_slots:
            break
        if take(e):
            got_fresh += 1
    for e in scored:
        if len(chosen) >= smax:
            break
        take(e)
    chosen.sort(key=lambda e: -float(e.get("_score", 0)))
    note = (f"{len(chosen)} chosen · {got_fresh} fresh-account slot(s) of "
            f"{fresh_slots} filled · per account: "
            + ", ".join(f"{a} {n}" for a, n in sorted(per_acct.items())))
    if len(chosen) < smin:
        note += f" · SHORT of {smin} (published honestly, no top-up)"
    return chosen, note
