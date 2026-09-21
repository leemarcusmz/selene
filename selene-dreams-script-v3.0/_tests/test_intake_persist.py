"""State must be saved when EITHER Drive intake or music intake changed it.
Added 2026-09-11: the tick saved only when a new VIDEO appeared, so tracks
added on a quiet tick were downloaded and their records discarded — then
re-downloaded every 15 minutes forever (33 tracks = 222 MB a tick)."""
import inspect, sys
sys.path.insert(0, ".")
import reel_runner

fails = 0
def check(l, c, e=""):
    global fails
    print(("  OK   " if c else "  FAIL ") + l + (f"  {e}" if e else ""))
    if not c: fails += 1

src = inspect.getsource(reel_runner.run)
check("music record count is measured around the sync",
      "before = len(state.get(\"music\"" in src and "after = len(state.get(\"music\"" in src)
check("the save is no longer gated on new videos alone",
      "if new or after != before:" in src)
check("the old gate is gone", "\n            if new:\n                save_state" not in src)

# behavioural: simulate both intakes
def simulate(new_videos, new_tracks):
    state = {"music": {"a": 1}}
    saved = []
    new = new_videos
    before = len(state.get("music", {}))
    for i in range(new_tracks):
        state["music"][f"t{i}"] = 1
    after = len(state.get("music", {}))
    if new or after != before:
        saved.append(True)
    return bool(saved)

check("new video only -> saves", simulate(1, 0))
check("new track only -> saves", simulate(0, 3))
check("both -> saves", simulate(2, 2))
check("neither -> does not save", not simulate(0, 0))

print(f"\n{'ALL PASS' if not fails else str(fails)+' FAILURE(S)'}")
sys.exit(1 if fails else 0)
