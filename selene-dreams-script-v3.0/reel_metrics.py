"""
reel_metrics.py — read Instagram results back for every published trial reel
=============================================================================
VERSION 1.2 — 2026-09-11

WHY THIS EXISTS
    The lane could publish and could log what it published, but nothing ever
    came back. `--variants` printed a views column full of em-dashes and said
    so honestly. A hook-variant experiment with no readback is not an
    experiment; it is a diary. This closes the loop.

THE THING I DID NOT KNOW WHEN I BUILT IT
    Media insights are documented for normal reels. Trial reels are a
    restricted-distribution format and I could NOT confirm they expose the same
    metrics — Cowork's proxy blocks graph.facebook.com, so I could not test
    against the live post before writing this.

    So this module does not assume. It NEGOTIATES:

      1. Ask for every metric we would like, in one call.
      2. If Instagram rejects the set, ask for each metric on its own and keep
         the ones that answer. Whatever survives is cached in
         _state/reels.json under "metrics_fields" and reused from then on, so
         the negotiation costs a handful of requests exactly once.
      2b. Negotiation only ever runs when the media node has JUST been read
         successfully. An expired token makes every metric fail, which is
         indistinguishable from "this format supports no metrics" — caching
         that would blind the readback permanently over a brief outage.

    3. Independently of insights, read like_count and comments_count off the
         MEDIA NODE itself. That is a different endpoint with different
         permissions, so even if trial reels expose no insights at all, likes
         and comments still land in the sheet.

    If the answer turns out to be "trial reels expose nothing", this module
    says so in the log, in plain words, once per media — rather than writing
    zeros, which would read as "nobody watched" instead of "we cannot see".

WHEN IT READS
    Twice per reel, on the windows in reel_config.METRIC_WINDOWS:
      ~72h — the trial window has closed and the non-follower test is over.
      ~7d  — the tail, which is where reels differ most from feed posts.
    A window is read once and then never again, so the numbers in the sheet
    are comparable across reels: every row is "the same age".

    An off-schedule reading (--metrics-now, for finding out what the API
    returns today) goes into the PROBE slot instead. It is a look, not a
    measurement: it never occupies a real window, so the scheduled 72h and 7d
    readings still happen on time. Nothing else in the lane is allowed to
    write to a window early either.

FAIL-OPEN, LIKE EVERYTHING ELSE IN THIS LANE
    Nothing here raises into the tick. A dead token, a rate limit, a metric
    that vanished in a Graph version bump — all of them log and return. The
    publishing path must never be able to fail because a READ failed.

CHANGELOG
    1.2  2026-09-11  An UNREADABLE window is retried. It held no number but
                     still counted as read, so a dead token at the 72h mark
                     would have cost that window permanently — the readback
                     failing quietly, which is the exact failure mode this lane
                     was built to avoid. Bounded by
                     reel_config.METRICS_UNREADABLE_RETRIES.
    1.1  2026-09-11  THE PROBE SLOT. --metrics-now used to write its reading
                     into EVERY configured window, including windows the reel
                     had not reached yet. Marcus ran it on a 45-hour-old reel
                     and it filled both "72h" and "7d" with the same 45h
                     number — and because a window is read once and never
                     re-read, the real 72h and 7d readings would never have
                     been taken. An off-schedule reading now lands in a
                     separate "probe" slot that blocks nothing. The comparability
                     rule this module is built on was the first thing my own
                     override broke.
    1.0  2026-09-10  First build.
=============================================================================
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

import reel_config

VERSION = "1.2"

# Where an off-schedule reading goes. Not a window: it blocks nothing, and
# nothing compares it to anything.
PROBE = "probe"

# Everything worth asking for. Order matters only for the log.
WANTED = [
    "views",              # replaced "plays"/"impressions" for reels in v22
    "reach",
    "likes",
    "comments",
    "shares",
    "saved",
    "total_interactions",
    "ig_reels_avg_watch_time",       # milliseconds
    "ig_reels_video_view_total_time",
]

# Read off the media node itself, not /insights. Different endpoint, different
# permission surface — this is the fallback that works when insights does not.
NODE_FIELDS = "like_count,comments_count,permalink,timestamp,media_product_type"


def log(msg):
    print(f"[reel_metrics] {msg}", flush=True)


# =============================================================================
# GRAPH
# =============================================================================

def _get(path, params):
    """GET against the Graph API. Raises; every caller catches."""
    import reel_runner
    payload = dict(params)
    payload["access_token"] = reel_runner.ig_token()
    url = f"{reel_runner.GRAPH}/{path}?{urllib.parse.urlencode(payload)}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:400]
        raise RuntimeError(f"{e.code}: {body}")


# =============================================================================
# METRIC NEGOTIATION
# =============================================================================

def _probe_fields(media_id):
    """Find out which metrics this account's reels actually answer for.

    Cheap path first: ask for everything in ONE call. Instagram answers the
    whole set or rejects the whole set, so when trial reels behave like normal
    reels this costs a single request. Only a rejection triggers the slow
    one-at-a-time walk, and only once — the result is cached in state.
    """
    try:
        r = _get(f"{media_id}/insights", {"metric": ",".join(WANTED)})
        names = [i.get("name") for i in r.get("data", []) if i.get("name")]
        if names:
            log(f"insight metrics supported: {', '.join(names)}")
            return names
    except Exception as e:
        log(f"the full metric set was rejected ({str(e)[:100]}) — "
            f"testing them one at a time (one-off, result is cached)")

    survivors = []
    for m in WANTED:
        try:
            r = _get(f"{media_id}/insights", {"metric": m})
            if r.get("data"):
                survivors.append(m)
        except Exception as e:
            log(f"  {m}: unsupported ({str(e)[:70]})")
    if survivors:
        log(f"  supported: {', '.join(survivors)}")
    else:
        log("  NO insight metric answered for this media. Trial reels appear "
            "not to expose /insights on this account. Likes and comments will "
            "still be read from the media node.")
    return survivors


def _insights(media_id, fields):
    """Fetch a known-good metric set. Returns {metric: value}."""
    if not fields:
        return {}
    r = _get(f"{media_id}/insights", {"metric": ",".join(fields)})
    out = {}
    for item in r.get("data", []):
        name = item.get("name")
        values = item.get("values") or [{}]
        out[name] = values[0].get("value")
    return out


def _node(media_id):
    """like_count / comments_count straight off the media object."""
    return _get(media_id, {"fields": NODE_FIELDS})


def fetch(media_id, state):
    """Everything readable about one published reel. Never raises.

    Returns a dict, possibly partial, possibly empty. An empty dict means
    nothing at all could be read — which is recorded as such, not as zeros.
    """
    result = {}

    # 1. The media node. Works with basic permissions, and doubles as the
    #    reachability test for step 2.
    node_ok = False
    try:
        node = _node(media_id)
        node_ok = True
        if node.get("like_count") is not None:
            result["likes"] = node["like_count"]
        if node.get("comments_count") is not None:
            result["comments"] = node["comments_count"]
        if node.get("media_product_type"):
            result["_product_type"] = node["media_product_type"]
    except Exception as e:
        log(f"media node unreadable for {media_id} ({str(e)[:120]})")

    # THE POISONED-CACHE TRAP, and why node_ok gates everything below.
    # An expired token makes every metric fail, which looks exactly like
    # "this account's trial reels support no metrics". Caching THAT would
    # permanently blind the readback over what was a two-minute outage. So
    # negotiation only happens when the node read just proved the API is
    # reachable and the token is alive. If it is not, we read nothing this
    # window and try again on the next tick, having spent one request rather
    # than ten.
    if not node_ok:
        return result

    # 2. Insights, using the cached metric set or negotiating one.
    fields = state.get("metrics_fields")
    if fields is None:
        fields = _probe_fields(media_id)
        state["metrics_fields"] = fields
        state["metrics_fields_at"] = datetime.now().isoformat(
            timespec="seconds")

    if fields:
        try:
            result.update({k: v for k, v in _insights(media_id, fields).items()
                           if v is not None})
        except Exception as e:
            # The cached set stopped working — a Graph version bump, most
            # likely. Renegotiate once, right now, rather than losing this
            # window. Safe to cache the answer: node_ok says the API is up.
            log(f"cached metric set failed ({str(e)[:120]}) — renegotiating")
            try:
                fields = _probe_fields(media_id)
                state["metrics_fields"] = fields
                state["metrics_fields_at"] = datetime.now().isoformat(
                    timespec="seconds")
                if fields:
                    result.update({k: v for k, v
                                   in _insights(media_id, fields).items()
                                   if v is not None})
            except Exception as e2:
                log(f"insights still unreadable ({str(e2)[:120]})")

    return result


# =============================================================================
# WINDOWS
# =============================================================================

def _parse(ts):
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def due_windows(run, now, force=False):
    """Which windows this run is ready for and has not had read.

    force does NOT mean "every window". A reading taken before a window has
    been reached is not that window's number, and writing it there would close
    the window forever on a value measured at the wrong age. So force returns
    the genuinely-due windows, plus PROBE when nothing is due — a slot that
    records the look without consuming a measurement.
    """
    posted = _parse(run.get("at", ""))
    if not posted:
        return []
    have = (run.get("metrics") or {})

    retries = getattr(reel_config, "METRICS_UNREADABLE_RETRIES", 5)

    def unread(label):
        """A window with no NUMBER in it is not a measurement, whatever it says.

        A failed read used to occupy the window anyway, so a dead token at the
        72h mark lost that window for good — the readback failing silently,
        which is the whole failure mode this lane exists to avoid.
        """
        entry = have.get(label)
        if entry is None:
            return True
        if entry.get("readable"):
            return False
        return entry.get("attempts", 1) < retries

    due = [label for label, hours in reel_config.METRIC_WINDOWS
           if unread(label) and now - posted >= timedelta(hours=hours)]
    if due or not force:
        return due
    return [PROBE]


def pass_over(state, force=False, limit=None):
    """Read metrics for every published run that is due. Never raises.

    Returns the number of (run, window) readings taken. The caller saves state
    if this is non-zero.
    """
    import reel_runner
    now = reel_runner.now_local()
    taken = 0

    for h, rec in state.get("videos", {}).items():
        for run in rec.get("runs", []):
            media_id = run.get("media_id")
            if not media_id:
                continue
            for label in due_windows(run, now, force=force):
                try:
                    data = fetch(media_id, state)
                except Exception as e:
                    log(f"unexpected failure on {media_id} ({str(e)[:120]})")
                    continue

                reading = {k: v for k, v in data.items()
                           if not k.startswith("_")}
                entry = {
                    "read_at": now.isoformat(timespec="seconds"),
                    "readable": bool(reading),
                    **reading,
                }
                if not entry["readable"]:
                    prior = (run.get("metrics") or {}).get(label, {})
                    entry["attempts"] = prior.get("attempts", 0) + 1
                if label == PROBE:
                    # The age matters for a probe in a way it does not for a
                    # window: a window's age is its name.
                    posted = _parse(run.get("at", ""))
                    if posted:
                        entry["age_hours"] = round(
                            (now - posted).total_seconds() / 3600, 1)
                run.setdefault("metrics", {})[label] = entry
                taken += 1

                name = rec.get("filename", h)
                if reading:
                    log(f"{name} v{run.get('variant', '?')} @{label}: "
                        + ", ".join(f"{k} {v}" for k, v in sorted(
                            reading.items())))
                else:
                    log(f"{name} v{run.get('variant', '?')} @{label}: "
                        f"nothing readable — recorded as unreadable, "
                        f"NOT as zero")

                try:
                    import reel_sheet
                    reel_sheet.write_metrics(run)
                except Exception as e:
                    log(f"sheet not updated ({str(e)[:100]}) — "
                        f"the numbers are safe in _state/reels.json")

                if limit and taken >= limit:
                    return taken
    return taken


def repair_windows(state):
    """Demote any window reading that was taken before its window was reached.

    Needed because v1.0's --metrics-now wrote off-schedule numbers straight
    into the real windows. The reading itself is kept — it is real data, just
    not the measurement it was filed as — so it moves to the probe slot with
    its true age, and the window reopens.
    """
    import reel_runner
    now = reel_runner.now_local()
    hours = dict(reel_config.METRIC_WINDOWS)
    moved = 0

    for h, rec in state.get("videos", {}).items():
        for run in rec.get("runs", []):
            have = run.get("metrics") or {}
            posted = _parse(run.get("at", ""))
            if not have or not posted:
                continue
            for label in list(have):
                if label == PROBE or label not in hours:
                    continue
                read_at = _parse(have[label].get("read_at", ""))
                if not read_at:
                    continue
                age = (read_at - posted).total_seconds() / 3600
                if age >= hours[label]:
                    continue          # legitimately taken, leave it
                entry = dict(have.pop(label))
                entry["age_hours"] = round(age, 1)
                entry["was_filed_as"] = label
                # Keep the OLDEST probe if several windows collapse into one:
                # they are the same reading anyway.
                have.setdefault(PROBE, entry)
                moved += 1
                log(f"{rec.get('filename', h)} v{run.get('variant', '?')}: "
                    f"'{label}' was read at {age:.0f}h, before the window. "
                    f"Moved to probe; the real {label} reading will be taken "
                    f"on schedule.")
    return moved


def latest(run):
    """The most recent readable reading, real windows preferred over a probe."""
    have = run.get("metrics") or {}
    for label, _ in reversed(reel_config.METRIC_WINDOWS):
        if have.get(label, {}).get("readable"):
            return have[label]
    if have.get(PROBE, {}).get("readable"):
        return have[PROBE]
    return {}


# =============================================================================
# CLI
# =============================================================================

def report(state=None):
    import reel_runner
    state = state or reel_runner.load_state()
    rows = []
    for h, rec in state.get("videos", {}).items():
        for run in rec.get("runs", []):
            if run.get("media_id"):
                rows.append((rec.get("filename", h), run))
    if not rows:
        print("\nNo published trial reels yet.\n")
        return

    print(f"\nTRIAL REEL METRICS — {len(rows)} published reel(s)\n")
    fields = state.get("metrics_fields")
    if fields is None:
        print("  (metrics have never been read; nothing negotiated yet)\n")
    elif not fields:
        print("  NOTE: /insights answered for no metric on this account's "
              "trial reels.\n        Likes and comments come from the media "
              "node instead.\n")

    for name, run in sorted(rows, key=lambda r: r[1].get("at", "")):
        print(f"{name}  v{run.get('variant', '?')}  "
              f"[{run.get('hook_mode', '?')}]  {run.get('at', '')[:16]}")
        print(f"  hook: {run.get('hook', '')[:70]}")
        have = run.get("metrics") or {}
        if not have:
            print("  no window read yet")
        if have.get(PROBE):
            m = have[PROBE]
            age = m.get("age_hours")
            print(f"  probe at {age}h (a look, not a measurement): " + (
                ", ".join(f"{k} {v}" for k, v in sorted(m.items())
                          if k not in ("read_at", "readable", "age_hours"))
                if m.get("readable") else "unreadable"))
        for label, _ in reel_config.METRIC_WINDOWS:
            m = have.get(label)
            if not m:
                print(f"  {label:<5} not yet due")
            elif not m.get("readable"):
                n = m.get("attempts", 1)
                cap = getattr(reel_config, "METRICS_UNREADABLE_RETRIES", 5)
                more = (f", will retry ({n}/{cap})" if n < cap
                        else ", gave up after {} tries".format(cap))
                print(f"  {label:<5} unreadable at "
                      f"{m.get('read_at', '')[:16]}{more}")
            else:
                print(f"  {label:<5} " + ", ".join(
                    f"{k} {v}" for k, v in sorted(m.items())
                    if k not in ("read_at", "readable")))
        print()


if __name__ == "__main__":
    import sys
    import reel_runner
    st = reel_runner.load_state()
    if "--read" in sys.argv or "--force" in sys.argv:
        n = pass_over(st, force="--force" in sys.argv)
        reel_runner.save_state(st)
        print(f"\n{n} reading(s) taken.\n")
    report(st)
