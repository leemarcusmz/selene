import sys, copy
from datetime import datetime, timedelta, timezone
sys.path.insert(0, ".")
import reel_config, reel_metrics
HK = timezone(timedelta(hours=8)); NOW = datetime(2026,9,20,12,0,tzinfo=HK)
class FR:
    GRAPH="g"
    ig_token=staticmethod(lambda: "T"); now_local=staticmethod(lambda: NOW); load_state=staticmethod(lambda: {})
sys.modules["reel_runner"]=FR
class FS:
    write_metrics=staticmethod(lambda run: True)
sys.modules["reel_sheet"]=FS
def base():
    return {"videos":{"h1":{"filename":"clip.MP4","runs":[
        {"at":"2026-09-09T18:42:51+08:00","variant":1,"hook_mode":"caption",
         "media_id":"MID1","permalink":"p"}]}},"posts":[]}
fails=0
def check(l,c,e=""):
    global fails
    print(("  OK   " if c else "  FAIL ")+l+(f"  {e}" if e else ""))
    if not c: fails+=1

calls=[]
def dead(path,params):
    calls.append(path); raise RuntimeError("190: token expired")
reel_metrics._get=dead
st=base(); reel_metrics.pass_over(st)
check("dead token does NOT cache a metric set", st.get("metrics_fields") is None, str(st.get("metrics_fields")))
check("dead token costs 1 request per window, not 10", len(calls)==2, f"{len(calls)} calls")
check("window recorded unreadable", st["videos"]["h1"]["runs"][0]["metrics"]["72h"]["readable"] is False)

# recovery on a later tick
def good(path,params):
    if path=="MID1": return {"like_count":41,"comments_count":3}
    ms=params["metric"].split(",")
    return {"data":[{"name":m,"values":[{"value":9}]} for m in ms]}
reel_metrics._get=good
n=reel_metrics.pass_over(st)          # no force: an unreadable window is due again
check("recovers once the token is back", st["metrics_fields"]==reel_metrics.WANTED)
check("an unreadable window is retried WITHOUT force",
      st["videos"]["h1"]["runs"][0]["metrics"]["72h"]["readable"] is True)

# and the retry is bounded
reel_metrics._get = dead
st2 = base()
for _ in range(9):
    reel_metrics.pass_over(st2)
m = st2["videos"]["h1"]["runs"][0]["metrics"]["72h"]
check("unreadable retries are bounded", m["attempts"] == 5, str(m.get("attempts")))
check("gives up rather than retrying forever",
      reel_metrics.due_windows(st2["videos"]["h1"]["runs"][0], NOW) == [],
      str(reel_metrics.due_windows(st2["videos"]["h1"]["runs"][0], NOW)))

# one-call happy path
calls.clear()
def counting(path,params):
    calls.append(path)
    return good(path,params)
reel_metrics._get=counting
st2=base(); reel_metrics.pass_over(st2, limit=1)
check("negotiation costs at most one extra call, once ever", len(calls)<=3, f"{len(calls)} calls: {calls}")

print(f"\n{'ALL PASS' if not fails else str(fails)+' FAILURE(S)'}")
sys.exit(1 if fails else 0)
