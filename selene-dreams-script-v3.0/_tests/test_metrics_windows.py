"""Window scheduling and the probe slot. Added 2026-09-11 after --metrics-now
filled both real windows with a 45-hour reading on the first live use."""
import sys, copy
from datetime import datetime, timedelta, timezone
sys.path.insert(0, ".")
import reel_config, reel_metrics

HK = timezone(timedelta(hours=8))
NOW = datetime(2026, 9, 11, 16, 0, tzinfo=HK)
POSTED = "2026-09-09T18:42:51+08:00"          # 45.3h before NOW — the real case

class FR:
    GRAPH = "g"
    ig_token = staticmethod(lambda: "T")
    now_local = staticmethod(lambda: NOW)
    load_state = staticmethod(lambda: {})
sys.modules["reel_runner"] = FR
class FS:
    write_metrics = staticmethod(lambda run: True)
sys.modules["reel_sheet"] = FS

def base(at=POSTED):
    return {"videos": {"h1": {"filename": "clip.MP4", "runs": [
        {"at": at, "variant": 1, "hook_mode": "caption", "media_id": "MID1",
         "permalink": "p"}]}}, "posts": []}

def good(path, params):
    if path == "MID1": return {"like_count": 1, "comments_count": 0}
    return {"data": [{"name": m, "values": [{"value": 235}]}
                     for m in params["metric"].split(",")]}
reel_metrics._get = good

fails = 0
def check(l, c, e=""):
    global fails
    print(("  OK   " if c else "  FAIL ") + l + (f"  {e}" if e else ""))
    if not c: fails += 1

R = lambda st: st["videos"]["h1"]["runs"][0]

# --- the bug -----------------------------------------------------------------
st = base(); reel_metrics.pass_over(st, force=True)
m = R(st)["metrics"]
check("force at 45h does NOT fill 72h", "72h" not in m, str(list(m)))
check("force at 45h does NOT fill 7d", "7d" not in m, str(list(m)))
check("force records a probe instead", "probe" in m, str(list(m)))
check("probe records its true age", m["probe"]["age_hours"] == 45.3,
      str(m["probe"].get("age_hours")))
check("probe carries the numbers", m["probe"]["views"] == 235)

# the probe must not block the real window later
LATER = NOW + timedelta(hours=40)
FR.now_local = staticmethod(lambda: LATER)
check("72h is still due after a probe",
      reel_metrics.due_windows(R(st), LATER) == ["72h"],
      str(reel_metrics.due_windows(R(st), LATER)))
reel_metrics.pass_over(st)
check("real 72h reading lands", R(st)["metrics"]["72h"]["readable"] is True)
check("probe survives alongside it", "probe" in R(st)["metrics"])
check("a real window outranks the probe in latest()",
      reel_metrics.latest(R(st)) is R(st)["metrics"]["72h"])
FR.now_local = staticmethod(lambda: NOW)

# --- force when a window IS due: must use the window, not a probe ------------
st = base(at=(NOW - timedelta(hours=100)).isoformat())
reel_metrics.pass_over(st, force=True)
m = R(st)["metrics"]
check("force with 72h genuinely due fills 72h", "72h" in m, str(list(m)))
check("force does not also invent a probe", "probe" not in m, str(list(m)))
check("force does not reach into the undue 7d", "7d" not in m, str(list(m)))

# --- repair_windows: undo damage v1.0 already wrote --------------------------
st = base()
stamp = NOW.isoformat(timespec="seconds")
R(st)["metrics"] = {
    "72h": {"read_at": stamp, "readable": True, "views": 235},
    "7d":  {"read_at": stamp, "readable": True, "views": 235},
}
moved = reel_metrics.repair_windows(st)
m = R(st)["metrics"]
check("repair moved both premature windows", moved == 2, str(moved))
check("repair left a single probe", list(m) == ["probe"], str(list(m)))
check("repair kept the numbers", m["probe"]["views"] == 235)
check("repair recorded the true age", m["probe"]["age_hours"] == 45.3)
check("repair notes what it was mis-filed as", m["probe"]["was_filed_as"] in ("72h", "7d"))
check("both windows reopen",
      set(reel_metrics.due_windows(R(st), NOW + timedelta(hours=200)))
      == {"72h", "7d"})

# a legitimately-timed window must be left alone
st2 = base()
R(st2)["metrics"] = {"72h": {"read_at": (NOW + timedelta(hours=40)).isoformat(
    timespec="seconds"), "readable": True, "views": 300}}
check("repair leaves an on-time window alone", reel_metrics.repair_windows(st2) == 0)
check("repair is idempotent", reel_metrics.repair_windows(st) == 0)

print(f"\n{'ALL PASS' if not fails else str(fails)+' FAILURE(S)'}")
sys.exit(1 if fails else 0)
