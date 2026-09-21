"""The Videos control tab must actually control music.
Added 2026-09-11: maybe_add re-ran its own silence test and overrode the sheet,
so "Audio in video? = no" was ignored on any clip with faint audio."""
import sys, os
sys.path.insert(0, ".")
import reel_config, reel_music, reel_sheet

fails = 0
def check(l, c, e=""):
    global fails
    print(("  OK   " if c else "  FAIL ") + l + (f"  {e}" if e else ""))
    if not c: fails += 1

# a clip with faint-but-present audio: wind on drone footage
INFO = {"has_audio": True, "duration": 11.0}
class FakeHost:
    @staticmethod
    def is_effectively_silent(path, info=None): return False   # it hears the wind
    probe = staticmethod(lambda p: INFO)
sys.modules["video_host"] = FakeHost

mixed = []
reel_music.choose = lambda state: "/tracks/calm.mp3"
reel_music.add_track = lambda v, t, d, dur: (mixed.append(t), d)[1]

# v1.0 behaviour: the module decides for itself, and refuses
path, meta = reel_music.maybe_add("/v.mp4", "/w", INFO, {}, decided=False)
check("undecided: module still self-decides and skips", meta is None and not mixed)

# v1.1: the caller decided (sheet said no audio) — the module must obey
mixed.clear()
path, meta = reel_music.maybe_add("/v.mp4", "/w", INFO, {}, decided=True)
check("decided: sheet override wins over the silence test", len(mixed) == 1,
      str(mixed))

# and the runner's decision logic itself
def decide(sheet_audio, detected_silent):
    has_audio = sheet_audio if sheet_audio is not None else not detected_silent
    return {"music": not has_audio}

check("sheet 'no' on a noisy clip -> music ON",
      decide(False, False)["music"] is True)
check("sheet 'yes' on a silent clip -> music OFF",
      decide(True, True)["music"] is False)
check("sheet blank, silent -> music ON", decide(None, True)["music"] is True)
check("sheet blank, has audio -> music OFF", decide(None, False)["music"] is False)

# _tri, the thing that reads his cells
check("_tri reads yes", reel_sheet._tri("yes") is True)
check("_tri reads no", reel_sheet._tri(" NO ") is False)
check("_tri blank means auto", reel_sheet._tri("") is None)
check("_tri garbage means auto", reel_sheet._tri("maybe?") is None)

print(f"\n{'ALL PASS' if not fails else str(fails)+' FAILURE(S)'}")
sys.exit(1 if fails else 0)
