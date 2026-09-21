"""Download cap vs hosting cap. Added 2026-09-11 after a 105 MB 4K master was
refused for being too big to HOST, before the downscale that exists to fix that."""
import sys
sys.path.insert(0, ".")
import reel_config, video_host

fails = 0
def check(l, c, e=""):
    global fails
    print(("  OK   " if c else "  FAIL ") + l + (f"  {e}" if e else ""))
    if not c: fails += 1

MB = 1024 * 1024
def info(mb, w=3840, h=2160):
    return {"duration": 11.0, "bytes": int(mb * MB), "ratio": w / h,
            "width": w, "height": h, "vcodec": "h264", "acodec": "aac",
            "has_audio": True}

# the real file: "5. On bed model + moon.mp4"
ok, why = video_host.validate(info(105), stage="source")
check("105 MB 4K master passes the DOWNLOAD cap", ok, why)
ok, why = video_host.validate(info(105), stage="delivery")
check("105 MB would fail the HOSTING cap", not ok, why)
check("and says which cap it failed", "hosting cap" in (why or ""), why)

ok, why = video_host.validate(info(600), stage="source")
check("600 MB is refused even for download", not ok, why)
check("and says download cap", "download cap" in (why or ""), why)

ok, _ = video_host.validate(info(12, 1080, 1920), stage="delivery")
check("a normal 12 MB delivery passes", ok)

check("default stage is still delivery (old callers unchanged)",
      video_host.validate(info(105)) == video_host.validate(info(105), "delivery"))

check("hosting cap is the tighter of the two",
      reel_config.MAX_BYTES < reel_config.MAX_SOURCE_BYTES,
      f"{reel_config.MAX_BYTES} vs {reel_config.MAX_SOURCE_BYTES}")

# the non-size rules must behave identically at both stages
bad = info(10); bad["vcodec"] = "hevc"
check("codec rule applies at source stage",
      not video_host.validate(bad, "source")[0])
check("codec rule applies at delivery stage",
      not video_host.validate(bad, "delivery")[0])
short = info(10); short["duration"] = 1.5
check("duration floor applies at both",
      not video_host.validate(short, "source")[0]
      and not video_host.validate(short, "delivery")[0])

# and the Drive intake uses the download cap
import reel_drive, inspect
src = inspect.getsource(reel_drive._sync)   # sync() is now the lock wrapper
check("Drive intake checks MAX_SOURCE_BYTES", "MAX_SOURCE_BYTES" in src)
check("Drive intake no longer checks the hosting cap",
      "reel_config.MAX_BYTES" not in src)

print(f"\n{'ALL PASS' if not fails else str(fails)+' FAILURE(S)'}")
sys.exit(1 if fails else 0)
