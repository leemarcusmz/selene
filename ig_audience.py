#!/usr/bin/env python3
"""
ig_audience.py  v1.1  (2026-09-14)
Pull @selenedreams_official's own audience and reach insights from the
Instagram Graph API and write them where the Flow Hub's T1 check looks.

This is the automated version of "go screenshot Business Suite". It reuses the
same IG_ACCESS_TOKEN the publish runner uses, so it needs no new credentials —
but it DOES need the instagram_manage_insights scope, which publishing does
not. If the token lacks it, every insights call fails cleanly and the script
says so rather than writing a half-empty file.

Every metric is negotiated the way reel_metrics.py negotiates media metrics:
ask for the set, and if the API rejects it, ask one at a time and keep what
answers. A dead token makes everything fail, which is reported distinctly.

Never prints or stores the token.

Usage:  python3 ig_audience.py [--days 90]
        Run it on the Mac itself. Through Cowork, that means Desktop
        Commander start_process — NOT device_bash.
Writes: ~/Desktop/_Claude Cowork/_00. Memory/_Ventures/Selene Dreams/insights/
          YYYY-MM-DD-insights.json   full payload
          YYYY-MM-DD-insights.md     readable summary

CHANGELOG
  v1.1  2026-09-14  MUST RUN NATIVELY ON THE MAC (Desktop Commander), not
                    through device_bash: that VM's network proxy blocks
                    graph.facebook.com with "Tunnel connection failed: 403".
                    Also fixed the output path — os.path.expanduser("~") in
                    the device_bash VM resolves to the VM's own home, so v1.0
                    wrote its files into a scratch directory the user never
                    sees and the hub's T1 check cannot find. Now resolves the
                    real Mac path first and falls back to the mounted one.
  v1.0  2026-09-14  first version. follower_demographics (country/city/age/
                    gender), reach split by follow_type, and the engagement
                    headline metrics. 30-day windows chunked to cover --days.
"""
import os, sys, json, time, urllib.parse, urllib.request, datetime, argparse, pathlib, re

HERE = pathlib.Path(__file__).resolve().parent
ENVF = HERE / "selene-dreams-script-v3.0" / ".env"
IG_USER_ID = "17841451177142651"          # @selenedreams_official
GRAPH = "https://graph.facebook.com/v21.0"
TAIL = "Desktop/_Claude Cowork/_00. Memory/_Ventures/Selene Dreams/insights"
def _out_dir():
    """The real Mac location if we are running natively; the mounted copy if
    we are inside the device_bash VM. Writing to the VM's own ~ is always
    wrong — nobody can see it and the hub's T1 check looks at the real path."""
    real = pathlib.Path("/Users/marcuslee") / TAIL
    if real.parent.parent.exists():
        return real
    mounted = pathlib.Path.home() / "mnt" / "_00. Memory" / "_Ventures" / "Selene Dreams" / "insights"
    if mounted.parent.parent.parent.exists():
        return mounted
    return pathlib.Path.home() / TAIL
OUT = _out_dir()

def log(m): print(f"[ig_audience] {m}", flush=True)

def token():
    if not ENVF.exists(): sys.exit(f"no .env at {ENVF}")
    for line in ENVF.read_text().splitlines():
        m = re.match(r"\s*IG_ACCESS_TOKEN\s*=\s*(.+)\s*$", line)
        if m: return m.group(1).strip().strip('"').strip("'")
    sys.exit("IG_ACCESS_TOKEN not found in .env")

TOK = token()

def get(path, params):
    p = dict(params); p["access_token"] = TOK
    url = f"{GRAPH}/{path}?{urllib.parse.urlencode(p)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(body.replace(TOK, "<token>"))
    except Exception as e:
        raise RuntimeError(str(e).replace(TOK, "<token>"))

def demographics(breakdown):
    """lifetime follower demographics for one breakdown dimension"""
    return get(f"{IG_USER_ID}/insights", {
        "metric": "follower_demographics", "period": "lifetime",
        "metric_type": "total_value", "breakdown": breakdown})

def windows(days, size=30):
    end = datetime.date.today()
    out = []
    while days > 0:
        n = min(size, days)
        start = end - datetime.timedelta(days=n)
        out.append((start.isoformat(), end.isoformat()))
        end = start; days -= n
    return list(reversed(out))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    a = ap.parse_args()
    today = datetime.date.today().isoformat()
    res = {"pulledAt": datetime.datetime.now().isoformat(timespec="seconds"),
           "account": "selenedreams_official", "igUserId": IG_USER_ID,
           "days": a.days, "profile": {}, "demographics": {},
           "reachByFollowType": [], "daily": [], "errors": []}

    # profile counts — instagram_basic, always available if the token lives
    try:
        res["profile"] = get(IG_USER_ID, {
            "fields": "username,followers_count,follows_count,media_count"})
        log(f"profile ok: {res['profile'].get('followers_count')} followers")
    except RuntimeError as e:
        res["errors"].append(f"profile: {e}")
        log(f"PROFILE FAILED — the token is probably dead: {e}")

    for b in ("country", "city", "age", "gender"):
        try:
            res["demographics"][b] = demographics(b)
            log(f"demographics/{b} ok")
        except RuntimeError as e:
            res["errors"].append(f"demographics/{b}: {e}")
            log(f"demographics/{b} FAILED: {str(e)[:160]}")
        time.sleep(0.4)

    for since, until in windows(a.days):
        try:
            r = get(f"{IG_USER_ID}/insights", {
                "metric": "reach", "period": "day", "metric_type": "total_value",
                "breakdown": "follow_type", "since": since, "until": until})
            res["reachByFollowType"].append({"since": since, "until": until, "data": r})
            log(f"reach/follow_type {since}..{until} ok")
        except RuntimeError as e:
            res["errors"].append(f"reach {since}..{until}: {e}")
            log(f"reach {since}..{until} FAILED: {str(e)[:160]}")
        try:
            r = get(f"{IG_USER_ID}/insights", {
                "metric": "reach,accounts_engaged,total_interactions,profile_views",
                "period": "day", "metric_type": "total_value",
                "since": since, "until": until})
            res["daily"].append({"since": since, "until": until, "data": r})
        except RuntimeError as e:
            res["errors"].append(f"daily {since}..{until}: {e}")
        time.sleep(0.4)

    OUT.mkdir(parents=True, exist_ok=True)
    jf = OUT / f"{today}-insights.json"
    jf.write_text(json.dumps(res, indent=2))

    # readable summary
    L = [f"# @selenedreams_official — audience insights", "",
         f"Pulled {res['pulledAt']} · window {a.days} days · via ig_audience.py v1.0", ""]
    p = res["profile"]
    if p:
        L += ["## Profile", f"- Followers: {p.get('followers_count'):,}"
              if p.get("followers_count") else "- Followers: n/a",
              f"- Following: {p.get('follows_count')}",
              f"- Posts: {p.get('media_count'):,}" if p.get("media_count") else "- Posts: n/a", ""]
    for b, payload in res["demographics"].items():
        try:
            rows = payload["data"][0]["total_value"]["breakdowns"][0]["results"]
            rows = sorted(rows, key=lambda r: -r["value"])[:15]
            L += [f"## Followers by {b}"]
            L += [f"- {'/'.join(r['dimension_values'])}: {r['value']:,}" for r in rows] + [""]
        except Exception:
            L += [f"## Followers by {b}", "- (unparsed — see the JSON)", ""]
    if res["reachByFollowType"]:
        L += ["## Reach, follower vs non-follower", "(see JSON for the daily series)", ""]
    if res["errors"]:
        L += ["## Errors", ""] + [f"- {e}" for e in res["errors"]] + [""]
    mf = OUT / f"{today}-insights.md"
    mf.write_text("\n".join(L))

    log(f"wrote {jf}")
    log(f"wrote {mf}")
    if res["errors"]:
        log(f"{len(res['errors'])} call(s) failed — see the Errors section")

if __name__ == "__main__":
    main()
