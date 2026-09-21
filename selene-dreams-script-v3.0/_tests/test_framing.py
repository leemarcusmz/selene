"""9:16 composition. Geometry only — no ffmpeg, so this runs anywhere.
Added 2026-09-11 with reel_framing 1.0."""
import sys
sys.path.insert(0, ".")
import reel_config, reel_framing, hook_overlay

fails = 0
def check(l, c, e=""):
    global fails
    print(("  OK   " if c else "  FAIL ") + l + (f"  {e}" if e else ""))
    if not c: fails += 1

def info(w, h, a=True):
    return {"width": w, "height": h, "has_audio": a, "duration": 10.0}

# --- what gets touched -------------------------------------------------------
check("1080x1920 left alone", reel_framing.decide(info(1080, 1920)) == "none")
check("drone 1728x3072 left alone", reel_framing.decide(info(1728, 3072)) == "none")
check("3840x2160 defaults to fit", reel_framing.decide(info(3840, 2160)) == "fit")
check("4:3 framed too", reel_framing.decide(info(1440, 1080)) == "fit")
check("sheet 'crop' overrides the default",
      reel_framing.decide(info(3840, 2160), "crop") == "crop")
check("sheet override applies to vertical sources too",
      reel_framing.decide(info(1080, 1920), "fit") == "fit")
check("garbage in the cell falls back to auto",
      reel_framing.decide(info(3840, 2160), "sideways") == "fit")

# --- crop --------------------------------------------------------------------
p = reel_framing.plan(info(3840, 2160), "crop")
check("16:9 crop keeps 32% of the width", p["kept_width_pct"] == 32,
      str(p["kept_width_pct"]))
check("crop fills the canvas height", p["scaled_h"] == reel_config.CANVAS_H)
check("crop window is centred",
      p["crop_x"] == (p["scaled_w"] - reel_config.CANVAS_W) // 2)
check("crop leaves the hook on the footage", p["hook_on_field"] is False)

# --- fit ---------------------------------------------------------------------
p = reel_framing.plan(info(3840, 2160), "fit")
check("fit video band is 608px", p["vid_h"] == 608, str(p["vid_h"]))
check("bands sum to the canvas",
      p["band_top_h"] + p["vid_h"] + p["band_bottom_h"] == reel_config.CANVAS_H,
      f"{p['band_top_h']}+{p['vid_h']}+{p['band_bottom_h']}")
check("h264-safe even dimensions", p["vid_h"] % 2 == 0 and p["top"] % 2 == 0)
H = reel_config.CANVAS_H
vid_bottom = (p["top"] + p["vid_h"]) / H
if p.get("hook_position") == "below":
    # 1.1 layout: hook starts under the footage and ends above IG's caption zone
    check("hook starts below the footage (+gap)",
          p["hook_y_frac"] >= vid_bottom + reel_config.FIT_HOOK_GAP_PX / H - 0.001,
          f"y={p['hook_y_frac']} footage ends {vid_bottom:.4f}")
    check("hook ends above the Instagram caption zone",
          p["hook_y_frac"] + p["hook_band_frac"] <= reel_config.IG_SAFE_BOTTOM_FRAC + 0.001,
          f"end={p['hook_y_frac'] + p['hook_band_frac']:.4f} <= {reel_config.IG_SAFE_BOTTOM_FRAC}")
    check("hook band tall enough for two lines",
          p["hook_band_frac"] * H >= 2.4 * reel_config.HOOK_SIZE_FRAC * reel_config.CANVAS_W,
          f"{p['hook_band_frac'] * H:.0f}px")
else:
    check("hook fits inside the upper field",
          p["hook_y_frac"] + p["hook_band_frac"]
          <= p["band_top_h"] / reel_config.CANVAS_H + 0.001,
          f"y={p['hook_y_frac']} h={p['hook_band_frac']}")
check("hook clears the Instagram top chrome (~10%)", p["hook_y_frac"] >= 0.06,
      str(p["hook_y_frac"]))
check("footage clears the Instagram bottom chrome (~from 66%)",
      (p["top"] + p["vid_h"]) / reel_config.CANVAS_H <= 0.68,
      str((p["top"] + p["vid_h"]) / reel_config.CANVAS_H))
check("fit flags the hook onto the field", p["hook_on_field"] is True)

# a source TALLER than 9:16 cannot be fitted; it must crop instead
check("taller-than-canvas falls back to crop",
      reel_framing.plan(info(1080, 2400), "fit")["mode"] == "crop")

# --- the field is legible ----------------------------------------------------
moss = (0x27, 0x3F, 0x22)
for name, ink in (("ecru", (0xE8, 0xE4, 0xD8)),
                  ("winter white", (0xF5, 0xF3, 0xEF))):
    c = hook_overlay.contrast_ratio(ink, moss)
    check(f"{name} on moss clears WCAG AA ({c:.1f}:1)", c >= 4.5)

t = hook_overlay.choose_treatment(moss, moss)
check("a flat moss field yields a treatment", t is not None)
check("and needs no scrim", t and t["scrim"] == 0, str(t and t["scrim"]))

# --- describe ----------------------------------------------------------------
check("describe handles None", reel_framing.describe(None) == "already 9:16")
check("describe names the crop loss",
      "32%" in reel_framing.describe(reel_framing.plan(info(3840, 2160), "crop")))

print(f"\n{'ALL PASS' if not fails else str(fails)+' FAILURE(S)'}")
sys.exit(1 if fails else 0)
