import sys, json, copy
from datetime import datetime, timedelta, timezone
sys.path.insert(0, ".")
import reel_config, reel_metrics

HK = timezone(timedelta(hours=8))
NOW = datetime(2026, 9, 20, 12, 0, tzinfo=HK)

class FakeRunner:
    GRAPH = "https://graph.facebook.com/v21.0"
    @staticmethod
    def ig_token(): return "TOK"
    @staticmethod
    def now_local(): return NOW
    @staticmethod
    def load_state(): return {}
sys.modules["reel_runner"] = FakeRunner

class FakeSheet:
    calls = []
    @staticmethod
    def write_metrics(run):
        FakeSheet.calls.append(copy.deepcopy(run.get("metrics")))
        return True
sys.modules["reel_sheet"] = FakeSheet

def base_state():
    return {"videos": {"h1": {"filename": "clip.MP4", "runs": [
        {"at": "2026-09-09T18:42:51+08:00", "variant": 1, "hook_mode": "caption",
         "hook": "A gauze blanket that fills the air.", "media_id": "MID1",
         "permalink": "https://instagram.com/reel/X"},
    ]}}, "posts": []}

fails = 0
def check(label, cond, extra=""):
    global fails
    print(("  OK   " if cond else "  FAIL ") + label + (f"  {extra}" if extra else ""))
    if not cond: fails += 1

# --- A: everything works -----------------------------------------------------
def get_all_good(path, params):
    if path == "MID1":
        return {"like_count": 41, "comments_count": 3,
                "media_product_type": "REELS", "permalink": "p"}
    if path.endswith("/insights"):
        ms = params["metric"].split(",")
        return {"data": [{"name": m, "values": [{"value": 100 + i}]}
                         for i, m in enumerate(ms)]}
    raise RuntimeError("unexpected")

reel_metrics._get = get_all_good
st = base_state()
n = reel_metrics.pass_over(st)
run = st["videos"]["h1"]["runs"][0]
check("A: both windows read (posted 11d ago)", n == 2, f"n={n}")
check("A: 72h readable", run["metrics"]["72h"]["readable"])
check("A: views present", run["metrics"]["72h"].get("views") is not None)
check("A: metric set cached", st.get("metrics_fields") == reel_metrics.WANTED)
check("A: re-run takes nothing", reel_metrics.pass_over(st) == 0)
check("A: sheet written twice", len(FakeSheet.calls) == 2, str(len(FakeSheet.calls)))

# --- B: insights dead entirely, node alive ----------------------------------
def get_no_insights(path, params):
    if path == "MID1":
        return {"like_count": 41, "comments_count": 3}
    raise RuntimeError("400: (#100) Insights not available for this media")

reel_metrics._get = get_no_insights
st = base_state()
reel_metrics.pass_over(st)
m = st["videos"]["h1"]["runs"][0]["metrics"]["72h"]
check("B: negotiation found nothing", st["metrics_fields"] == [], str(st["metrics_fields"]))
check("B: likes still read from node", m.get("likes") == 41)
check("B: marked readable (we got something)", m["readable"] is True)
check("B: no zero views invented", "views" not in m)

# --- C: nothing readable at all ---------------------------------------------
def get_dead(path, params): raise RuntimeError("190: token expired")
reel_metrics._get = get_dead
st = base_state()
reel_metrics.pass_over(st)
m = st["videos"]["h1"]["runs"][0]["metrics"]["72h"]
check("C: recorded unreadable, not zero",
      m["readable"] is False and "views" not in m and "likes" not in m, str(m))

# --- D: partial support, negotiated one by one -------------------------------
SUPPORTED = {"reach", "likes", "comments", "saved"}
def get_partial(path, params):
    if path == "MID1": return {"like_count": 41, "comments_count": 3}
    ms = params["metric"].split(",")
    if any(m not in SUPPORTED for m in ms):
        raise RuntimeError("400: (#100) metric must be one of ...")
    return {"data": [{"name": m, "values": [{"value": 7}]} for m in ms]}
reel_metrics._get = get_partial
st = base_state()
reel_metrics.pass_over(st)
check("D: negotiated down to supported set",
      set(st["metrics_fields"]) == SUPPORTED, str(st["metrics_fields"]))
check("D: reach present", st["videos"]["h1"]["runs"][0]["metrics"]["72h"].get("reach") == 7)

# --- E: window scheduling ----------------------------------------------------
st = base_state()
st["videos"]["h1"]["runs"][0]["at"] = (NOW - timedelta(hours=20)).isoformat()
check("E: nothing due at 20h", reel_metrics.due_windows(st["videos"]["h1"]["runs"][0], NOW) == [])
st["videos"]["h1"]["runs"][0]["at"] = (NOW - timedelta(hours=80)).isoformat()
check("E: 72h due at 80h, 7d not",
      reel_metrics.due_windows(st["videos"]["h1"]["runs"][0], NOW) == ["72h"])
# CORRECTED 2026-09-11. This used to assert force==all windows, which is the
# bug: at 80h the 7d number does not exist yet, and filling that window would
# close it forever on a reading taken at the wrong age.
check("E: force takes the due window only, never the undue one",
      reel_metrics.due_windows(st["videos"]["h1"]["runs"][0], NOW, force=True) == ["72h"])

# --- F: limit ----------------------------------------------------------------
reel_metrics._get = get_all_good
st = base_state()
check("F: limit respected", reel_metrics.pass_over(st, limit=1) == 1)

# --- G: no media_id (dry-run rows) -------------------------------------------
st = base_state(); del st["videos"]["h1"]["runs"][0]["media_id"]
check("G: rows without media_id skipped", reel_metrics.pass_over(st) == 0)

# --- H: report doesn't crash -------------------------------------------------
import io, contextlib
st = base_state(); reel_metrics.pass_over(st)
with contextlib.redirect_stdout(io.StringIO()) as buf:
    reel_metrics.report(st)
check("H: report renders", "TRIAL REEL METRICS" in buf.getvalue())

print(f"\n{'ALL PASS' if not fails else str(fails) + ' FAILURE(S)'}")
sys.exit(1 if fails else 0)
