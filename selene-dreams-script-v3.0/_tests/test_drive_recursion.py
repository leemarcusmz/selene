import sys; sys.path.insert(0,".")
import reel_drive
fails=0
def check(l,c,e=""):
    global fails
    print(("  OK   " if c else "  FAIL ")+l+(f"  {e}" if e else ""))
    if not c: fails+=1

# a fake Drive: top folder -> _New Zealand Shoot -> _Horizontal (7 clips)
TREE = {
  "TOP":  {"folders": [("NZ", "_New Zealand Shoot")], "videos": ["loose.mp4"]},
  "NZ":   {"folders": [("H", "_Horizontal"), ("V", "_Veritcal")], "videos": []},
  "H":    {"folders": [], "videos": [f"{i}. clip.mp4" for i in range(1, 8)]},
  "V":    {"folders": [], "videos": []},
}
calls = []
class FakeFiles:
    def list(self, q=None, **kw):
        calls.append(q)
        parent = q.split("'")[1]
        node = TREE.get(parent, {"folders": [], "videos": []})
        if "application/vnd.google-apps.folder" in q:
            items = [{"id": i, "name": n} for i, n in node["folders"]]
        else:
            items = [{"id": f"{parent}:{v}", "name": v, "mimeType": "video/mp4",
                      "size": "1000", "modifiedTime": "t"} for v in node["videos"]]
        class R:
            def execute(self_inner): return {"files": items}
        return R()
class FakeDrive:
    def files(self): return FakeFiles()

got = reel_drive.list_videos(FakeDrive(), "TOP")
names = sorted(f["name"] for f in got)
check("finds nested videos two levels down", len(got) == 8, f"{len(got)}: {names}")
check("still finds loose top-level files", "loose.mp4" in names)
paths = {f["name"]: f["rel_path"] for f in got}
check("records the subfolder path",
      paths["1. clip.mp4"] == "_New Zealand Shoot/_Horizontal", paths["1. clip.mp4"])
check("top-level file has empty path", paths["loose.mp4"] == "")
check("empty subfolder is harmless", True)

# depth cap
DEEP = {f"L{i}": {"folders": [(f"L{i+1}", f"lvl{i+1}")], "videos": [f"v{i}.mp4"]}
        for i in range(0, 9)}
TREE.clear(); TREE.update(DEEP)
calls.clear()
got = reel_drive.list_videos(FakeDrive(), "L0")
depths = sorted(f["rel_path"].count("/") for f in got)
check("depth cap stops the walk",
      max(f["rel_path"].count("/") + (1 if f["rel_path"] else 0) for f in got)
      <= reel_drive.MAX_FOLDER_DEPTH, str(depths))
check("bounded API calls", len(calls) <= 2 * (reel_drive.MAX_FOLDER_DEPTH + 1),
      f"{len(calls)} calls")

print(f"\n{'ALL PASS' if not fails else str(fails)+' FAILURE(S)'}")
sys.exit(1 if fails else 0)
