"""Stubbed test for reel_drive 1.6 withdrawal / restore / adoption. No network."""
import os, sys, tempfile, types
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
root = tempfile.mkdtemp()
os.environ["SELENE_CONTENT_DIR"] = root
import reel_config
reel_config.DROP_DIR = os.path.join(root, "drop"); reel_config.RETIRED_DIR = os.path.join(root, "retired")
os.makedirs(reel_config.DROP_DIR)
import reel_drive
FILES = []
reel_drive.list_videos = lambda svc, *a, **k: list(FILES)
dl = []
gs = types.ModuleType("google_services")
gs.download_file_from_drive = lambda svc, fid: (dl.append(fid), b"x" * 10)[1]
gs.get_drive_service = lambda: object()
sys.modules["google_services"] = gs
class L:
    held = True
    def __enter__(self): return self
    def __exit__(self, *a): pass
reel_drive._Lock = L
ok = 0; bad = 0
def check(name, cond):
    global ok, bad
    print(("PASS " if cond else "FAIL ") + name); ok += cond; bad += (not cond)
D = lambda n: os.path.exists(os.path.join(reel_config.DROP_DIR, n))
R = lambda n: os.path.exists(os.path.join(reel_config.RETIRED_DIR, n))
st = {}
FILES[:] = [{"id": f"f{i}", "name": f"v{i}.mp4", "size": "10"} for i in range(1, 5)]
reel_drive.sync(st, object())
check("4 new downloaded", len(dl) == 4 and all(D(f"v{i}.mp4") for i in range(1, 5)))
# hand-dropped local file
open(os.path.join(reel_config.DROP_DIR, "hand.mp4"), "wb").write(b"y" * 7)
FILES[:] = [f for f in FILES if f["id"] != "f2"]
reel_drive.sync(st, object())
check("removed from Drive -> moved to Retired", not D("v2.mp4") and R("v2.mp4"))
check("record marked withdrawn", bool(st["drive"]["f2"].get("withdrawn")))
check("hand-dropped file untouched", D("hand.mp4"))
check("others untouched", D("v1.mp4") and D("v3.mp4") and D("v4.mp4"))
FILES.append({"id": "f2", "name": "v2.mp4", "size": "10"})
n = len(dl); reel_drive.sync(st, object())
check("restored from Trash -> back in pool, no re-download", D("v2.mp4") and not R("v2.mp4") and len(dl) == n)
check("withdrawn flag cleared", not st["drive"]["f2"].get("withdrawn"))
# adoption: upload hand.mp4 to Drive with matching size
FILES.append({"id": "h1", "name": "hand.mp4", "size": "7"})
n = len(dl); reel_drive.sync(st, object())
check("adopted, no download, no _2 duplicate", len(dl) == n and st["drive"]["h1"].get("adopted") and not D("hand_2.mp4"))
# adoption refused on size mismatch
open(os.path.join(reel_config.DROP_DIR, "other.mp4"), "wb").write(b"z" * 3)
FILES.append({"id": "o1", "name": "other.mp4", "size": "99"})
reel_drive.sync(st, object())
check("size mismatch -> not adopted (downloaded as separate file)", not st["drive"]["o1"].get("adopted"))
# guard: empty listing
snap = list(FILES); FILES[:] = []
reel_drive.sync(st, object())
check("empty Drive listing -> nothing withdrawn", D("v1.mp4") and D("v3.mp4") and not any(r.get("withdrawn") for r in st["drive"].values()))
# guard: mass disappearance
FILES[:] = snap[:1]
reel_drive.sync(st, object())
check(">50% vanished -> nothing withdrawn", D("v3.mp4") and D("v4.mp4") and not any(r.get("withdrawn") for r in st["drive"].values()))
FILES[:] = snap
reel_drive.sync(st, object())
check("normal state afterwards: nothing withdrawn", not any(r.get("withdrawn") for r in st["drive"].values()))
print(f"\n{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
