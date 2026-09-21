import sys
sys.path.insert(0, ".")
import reel_config, reel_sheet

fails=0
def check(l,c,e=""):
    global fails
    print(("  OK   " if c else "  FAIL ")+l+(f"  {e}" if e else ""))
    if not c: fails+=1

class WS:
    def __init__(self, rows): self.rows=rows; self.writes=[]
    def get_all_values(self): return self.rows
    def row_values(self, n): return self.rows[n-1]
    def update(self, values=None, range_name=None, value_input_option=None):
        self.writes.append((range_name, values))

OLD_HEADER = reel_sheet.HEADERS[:17]          # the 17-column sheet as it exists
ROW = [""]*13
ROW[12] = "https://www.instagram.com/reel/DdEElE-jrbD/"
ROW += ["", "", "", "my note about this one"]  # N,O,P blank; Q = his note

ws = WS([OLD_HEADER, list(ROW)])
reel_sheet._open_tab = lambda title=None: ws

run = {"permalink": "https://www.instagram.com/reel/DdEElE-jrbD/",
       "media_id": "18112503980003981",
       "metrics": {"72h": {"read_at":"2026-09-12T18:00:00+08:00","readable":True,
                           "views":1240,"likes":41,"comments":3,"reach":1102,
                           "shares":7,"saved":12,
                           "ig_reels_avg_watch_time":4300}}}
ok = reel_sheet.write_metrics(run)
check("write_metrics succeeded", ok)
w = dict(ws.writes)
check("header row widened to 22", any(r=="A1" and len(v[0])==22 for r,v in ws.writes),
      str([ (r, len(v[0])) for r,v in ws.writes if r=="A1"]))
check("N:P written", "N2:P2" in w, str(list(w)))
check("views/likes/comments correct", w.get("N2:P2")==[[1240,41,3]], str(w.get("N2:P2")))
check("R:V written", w.get("R2:V2")==[[1102,7,12,4.3,"72h @ 2026-09-12 18:00"]],
      str(w.get("R2:V2")))
check("Q never in any written range", not any(r and "Q" in r for r,_ in ws.writes),
      str([r for r,_ in ws.writes]))

# unreadable window must not stamp zeros over a hand-typed number
ROW2 = [""]*13; ROW2[12]="p2"; ROW2 += ["999","","","note"]
ws2 = WS([OLD_HEADER, list(ROW2)]); reel_sheet._open_tab = lambda title=None: ws2
run2 = {"permalink":"p2","media_id":"m2",
        "metrics":{"72h":{"read_at":"2026-09-12T18:00:00+08:00","readable":False}}}
reel_sheet.write_metrics(run2)
w2 = dict(ws2.writes)
check("unreadable leaves the existing views value alone",
      w2.get("N2:P2")==[["999","",""]], str(w2.get("N2:P2")))
check("unreadable is stamped as such, not as 0",
      w2.get("R2:V2")[0][-1]=="72h: unreadable", str(w2.get("R2:V2")))

# newest window wins
run3 = dict(run2); run3["metrics"]={
  "72h":{"read_at":"a","readable":True,"views":10},
  "7d":{"read_at":"b","readable":True,"views":95}}
ws3 = WS([OLD_HEADER, list(ROW2)]); reel_sheet._open_tab = lambda title=None: ws3
reel_sheet.write_metrics(run3)
check("7d wins over 72h", dict(ws3.writes).get("N2:P2")[0][0]==95,
      str(dict(ws3.writes).get("N2:P2")))

# missing row: must not crash, must not write
ws4 = WS([OLD_HEADER]); reel_sheet._open_tab = lambda title=None: ws4
check("missing row returns False quietly", reel_sheet.write_metrics(run) is False)

# sheet down: fail-open
def boom(title=None): raise RuntimeError("503")
reel_sheet._open_tab = boom
check("sheet outage returns False, never raises", reel_sheet.write_metrics(run) is False)

print(f"\n{'ALL PASS' if not fails else str(fails)+' FAILURE(S)'}")
sys.exit(1 if fails else 0)
