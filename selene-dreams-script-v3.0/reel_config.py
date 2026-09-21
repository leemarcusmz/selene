"""
reel_config.py — settings for the trial-reel lane
=============================================================================
VERSION 1.13 — 2026-09-16

WHY THIS IS SEPARATE FROM config.py
    The trial-reel lane deliberately shares NO state with the carousel lane.
    It has no Google Sheet, no column protocol, no review screen. Keeping its
    settings in their own module means a change here can never break the
    generation or publishing flows that already run in production.

CHANGELOG
    1.13 2026-09-16  MARCUS'S THREE COMPLAINTS after reel DdVw6ebCvH0 (a
                     fitted 16:9 clip): the hook vanished after 2.6s, sat far
                     too high (centred in the upper brand field, ~8-26% of
                     the frame, under Instagram's own top UI), and the lane
                     kept picking the horizontal NZ clips. HOOK_DURATION=None
                     = whole clip. Fitted clips now sit higher
                     (FIT_VIDEO_Y_FRAC 0.40) with the hook BELOW the footage
                     in the lower field, kept above IG's caption zone
                     (FIT_HOOK_POSITION/FIT_HOOK_GAP_PX/IG_SAFE_BOTTOM_FRAC).
                     The ordering fix is in reel_runner 1.18.
    1.12 2026-09-16  FEEDBACK. TASTE_PATH, TASTE_TAB and the FEEDBACK_* knobs
                     for reel_feedback.py — Marcus's Notes/Rating on the
                     Trial Reels tab and the new Taste Notes tab now reach
                     the hook and caption writers. Feedback changes HOW a
                     reel is written, never WHETHER it publishes.
    1.11 2026-09-11  MAX_SOURCE_BYTES split out from MAX_BYTES. The 90 MB cap
                     exists because GitHub raw is not a CDN — but hosting
                     happens AFTER the delivery downscale, and the cap was
                     being applied BEFORE it, at Drive intake and again in
                     validate(). So a 105 MB 4K master was rejected for being
                     too big to host, despite downscaling to a fraction of that
                     before anything was hosted. "5. On bed model + moon.mp4"
                     is exactly this case. Two caps now: what we will DOWNLOAD,
                     and what we will HOST.
    1.10 2026-09-11  FRAMING. The New Zealand shoot is 16:9 and a reel is
                     watched at 9:16. Rather than converting the footage into a
                     second set of files, the lane now composes the 9:16 frame
                     at publish time — so the originals stay the only copy and
                     the treatment stays a decision that can be changed and
                     re-tested rather than baked into a file.
    1.9  2026-09-11  METRICS_UNREADABLE_RETRIES. A window that failed to read
                     held no number but still counted as read, so one bad
                     minute at the 72h mark lost that window for good. An
                     unreadable window is now retried on later ticks, a bounded
                     number of times.
    1.8  2026-09-10  METRIC_WINDOWS. The lane can now read Instagram results
                     back (reel_metrics.py). Two windows, not one: 72h closes
                     the trial's non-follower test, 7d catches the tail where
                     reels behave least like feed posts. A window is read once
                     and never re-read, so every row in the sheet is the same
                     age and the numbers are comparable across reels.
    1.7  2026-09-10  CLAIMS_PATH. Points at the educational lane's
                     prompts/claims_edu.md — the file Marcus created after
                     catching an unverified "GOTS 400TC" claim, and which is
                     already defined as the ONLY product facts copy may state.
                     Reusing it rather than starting a second list: two sources
                     of truth about the same products is how they drift apart.
    1.6  2026-09-10  HOOK_TEXT_WIDTH: hook wrapping is now measured against the
                     real font, so the text box is a fraction of frame width
                     rather than a 26-character guess. HOOK_WRAP_CHARS survives
                     only as a fallback when a font cannot be loaded.
    1.5  2026-09-09  Drive restructured by Marcus: "05. Trial Reel Videos" and
                     "06. Reel Music" became "05. Video Reel" with subfolders
                     "01. Video Content" and "02. Audio Content", so the same
                     source material can serve other flows. The folder ids moved
                     to the SHARED config.py for exactly that reason; this
                     module now references them rather than owning them.
    1.4  2026-09-09  MUSIC. Drive folder "06. Reel Music" + mixing settings.
                     OFF UNTIL THE FOLDER HAS TRACKS: an empty folder means
                     reels publish silent exactly as before, so this costs
                     nothing until Marcus decides to use it.
    1.3  2026-09-09  Sheet moved into Drive "10. AI Generation" (the folder
                     config.DRIVE_PARENT_FOLDER_ID already points at) and
                     recreated by CSV import so the header row exists without
                     needing the Sheets API, which Cowork's proxy blocks. New
                     file id; the original blank sheet was trashed.
    1.2  2026-09-09  SHEET MIRROR. Adds the "Selene Dreams - Trial Reel" sheet
                     id and tab name. The sheet is a READ-ONLY MIRROR, never a
                     source of truth: _state/reels.json still decides
                     everything, so a Sheets or Drive outage cannot stop a
                     trial reel from publishing. That property is why this lane
                     had no sheet at all until Marcus asked to see the hooks
                     and captions somewhere.
    1.1  2026-09-09  HOOK VARIANTS. Adds the hook bank path, the two application
                     modes (caption / overlay), overlay geometry and font
                     candidates, and the variant cadence rules.
                     DEFAULT IS "caption", on evidence: four top-engagement
                     bedding reels were opened by hand on 2026-09-09 (Brooklinen
                     x3, Parachute x1) and NONE burns a text hook onto the video.
                     Overlay is the challenger, kept because it is worth testing
                     precisely because the category does not do it.
    1.0  2026-09-09  First build.
=============================================================================
"""

import os

import config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── where Marcus drops videos ───────────────────────────────────────────────
# ABSOLUTE ON PURPOSE, and spelled the same way caption_runner.CAPTION_LOG_PATH
# spells it. "~" resolves somewhere else under launchd and under Cowork's shell,
# and a rotation log written to the wrong path is invisible rather than loud —
# the recency filter simply goes blind. reel_runner --doctor asserts that this
# module and caption_runner still agree, so the two can never drift apart
# unnoticed. Override both with SELENE_CAPTION_LOG when testing.
CONTENT_DIR = os.environ.get(
    "SELENE_CONTENT_DIR",
    "/Users/marcuslee/Desktop/Selene Dreams/03. Content")
REEL_ROOT = os.path.join(CONTENT_DIR, "04. Trial Reels")
DROP_DIR = os.path.join(REEL_ROOT, "00. Drop Here")
RETIRED_DIR = os.path.join(REEL_ROOT, "01. Retired")

CAPTION_LOG_PATH = os.environ.get(
    "SELENE_CAPTION_LOG",
    os.path.join(CONTENT_DIR, "00. Social Media Posts", "caption-log.md"))

STATE_PATH = os.path.join(BASE_DIR, "_state", "reels.json")
LOG_DIR = os.path.join(BASE_DIR, "_logs")
WORK_DIR = os.path.join(BASE_DIR, "_state", "reel-work")

# ── video constraints (Meta's Reels spec, tightened for our own hosting) ────
VIDEO_EXTS = (".mp4", ".mov", ".m4v")
MIN_DURATION = 3.0            # seconds — Meta's floor
MAX_DURATION = 900.0          # 15 minutes — Meta's ceiling
MAX_BYTES = 90 * 1024 * 1024  # HOSTING cap, checked after the downscale.
                              # GitHub raw is not a CDN.
MAX_SOURCE_BYTES = 500 * 1024 * 1024
# What the lane is willing to download and process. Generous on purpose: a 4K
# master is large and then downscales to a fraction of itself, so judging it by
# the hosting cap throws away usable footage for a reason that no longer applies
# by the time anything is hosted. This cap is about bandwidth and disk only.
MIN_RATIO = 0.01
MAX_RATIO = 10.0
PREFERRED_RATIO = 9 / 16

FRAME_COUNT = 6               # frames handed to the vision pass

# ── cadence ────────────────────────────────────────────────────────────────
# The lane picks its own moments. These bound it so it can never run away.
MIN_HOURS_BETWEEN_POSTS = 40      # never two trials closer than this
MAX_POSTS_PER_DAY = 1             # hard ceiling regardless of stock
POSTING_HOURS = (10, 21)          # local hours it is allowed to fire in
TIMEZONE = "Asia/Hong_Kong"

# REPOST COOLDOWN — Marcus's call 2026-09-09. He has not seen duplicate
# suppression on his own account, so re-posting the same file is ALLOWED,
# but only after a long gap and only a bounded number of times. If reach
# collapses on second runs, raise the cooldown rather than removing it.
REPOST_COOLDOWN_DAYS = 45
MAX_RUNS_PER_VIDEO = 3

# ── publishing ─────────────────────────────────────────────────────────────
GRADUATION_STRATEGY = "MANUAL"    # never SS_PERFORMANCE without Marcus saying so
PUBLIC_REPO_PREFIX = "reels"      # path inside the selene-ig-public repo

# ── caption ────────────────────────────────────────────────────────────────
# Reel routing, settled 2026-09-09 (the decision deferred on 2026-09-07).
# Trial reels reach ONLY non-followers, i.e. a cold audience that has never
# heard of Selene. Explaining styles assume a reader who already cares, so
# they are excluded; the video has already delivered the detail.
REEL_ELIGIBLE_STYLES = ["One Line", "Two Beat", "Meet the Product"]
REEL_STYLE_NO_REPEAT_WITHIN = 3

# ── verified product facts ─────────────────────────────────────────────────
# The educational lane's claims file, reused deliberately. It exists because
# Marcus caught an unverified "GOTS 400TC" claim on 2026-09-07, and it is
# already the single source of truth for what copy may assert. A second list
# would only drift from this one.
CLAIMS_PATH = os.path.normpath(os.path.join(
    BASE_DIR, "..", "selene-dreams-educational-v1.0", "prompts",
    "claims_edu.md"))

# ── the mirror sheet ───────────────────────────────────────────────────────
# "Selene Dreams - Trial Reel", in Drive: Selene Bedding / 10. AI Generation
# (same folder as the other queue sheets, = DRIVE_PARENT_FOLDER_ID).
# Created in MARCUS'S OWN Drive and then shared with the service account as
# writer. That order matters: a service-account-created file is OWNED by the
# service account, lives in a Drive nobody can browse, and never appears in his.
# It was imported from a header-row CSV, so the columns exist without the
# Sheets API — which Cowork's proxy blocks (oauth2.googleapis.com 403).
# Side effect of CSV import: the first tab is named "Untitled".
# setup_reel_sheet.py RENAMES it rather than adding a second tab.
REEL_SHEET_ID = "1HKg5YiC_vRFKtsbo2KleH5KXxCaWgWsqyvDhETdhuEQ"
REEL_SHEET_TAB = "Trial Reels"
REEL_SHEET_URL = f"https://docs.google.com/spreadsheets/d/{REEL_SHEET_ID}/edit"

# ── feedback: what Marcus said about earlier reels ─────────────────────────
# Read from the same sheet (Trial Reels: Q Notes + W Rating; Taste Notes tab)
# by reel_feedback.py, kept in reels.json, and injected into the writer
# prompts. Fail-open like the control tab: sheet down -> last-read feedback.
TASTE_TAB = "Taste Notes"
TASTE_PATH = os.path.join(CONTENT_DIR, "00. Social Media Posts",
                          "reel-taste.md")
FEEDBACK_MAX_ITEMS = 12       # newest rated/commented reels shown to writers
FEEDBACK_MAX_CHARS = 2400     # hard cap on the injected block
# A hook PATTERN averaging this or below over at least FEEDBACK_MIN_RATINGS
# ratings leaves the rotation. It does not stop anything publishing.
FEEDBACK_LOW_RATING = 2.0
FEEDBACK_MIN_RATINGS = 2
FEEDBACK_ON_TICK = True

# ── music ──────────────────────────────────────────────────────────────────
# Drive: 10. AI Generation / 05. Video Reel / 02. Audio Content.
# EMPTY = no music, publish silent.
# ONLY licensed or owned audio belongs here (Artlist). Instagram-library music
# cannot be attached through the API and ripping it is a rights problem, not a
# technical one — see [[selene-ig-api-limits]].
MUSIC_FOLDER_ID = config.DRIVE_AUDIO_CONTENT_FOLDER_ID
MUSIC_FOLDER_URL = f"https://drive.google.com/drive/folders/{MUSIC_FOLDER_ID}"
MUSIC_DIR = os.path.join(BASE_DIR, "_state", "reel-music")
MUSIC_EXTS = (".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg")

# Music is added ONLY when the video has nothing audible. Real location sound is
# never overwritten — that would be destroying something Marcus shot.
MUSIC_ONLY_WHEN_SILENT = True
MUSIC_TARGET_LUFS = -14.0     # the loudness social platforms normalise toward
MUSIC_FADE_OUT = 1.2          # seconds, so a hard cut never lands on the end
MUSIC_NO_REPEAT_WITHIN = 3    # do not reuse a track within this many reels

# ── hooks ──────────────────────────────────────────────────────────────────
HOOK_BANK_PATH = os.path.join(
    CONTENT_DIR, "00. Social Media Posts", "hook-bank-v1.0.md")

# "caption" = the hook is the caption's first line, video untouched.
# "overlay" = the hook is burned into the opening seconds.
# Evidence says caption. Flip to "overlay" to make burn-in the default, or set
# HOOK_MODE_ROTATION to alternate and let the results decide.
HOOK_MODE = "caption"
HOOK_MODE_ROTATION = ["caption", "caption", "overlay"]  # used when HOOK_ROTATE
HOOK_ROTATE = True     # alternate modes so the two can be compared at all

MAX_VARIANTS_PER_VIDEO = 3       # distinct hooks cut from one source video
VARIANT_COOLDOWN_DAYS = 14       # between variants of the SAME source video
                                 # (shorter than REPOST_COOLDOWN_DAYS: a new
                                 #  hook is a new post, not a repeat)

# ── overlay geometry ───────────────────────────────────────────────────────
HOOK_DURATION = None       # seconds the hook stays on screen; None = the WHOLE
                           # clip (Marcus, 2026-09-16: it "briefly appears and
                           # then disappears" at 2.6s). Set a number to go back.
HOOK_FADE = 0.35           # in/out fade
HOOK_Y_FRAC = 0.30         # top of the text band, fraction of frame height
HOOK_BAND_FRAC = 0.22      # band height — also the luminance sample window
HOOK_SIZE_FRAC = 0.062     # font size as a fraction of frame WIDTH
HOOK_TEXT_WIDTH = 0.78     # text box as a fraction of frame width
HOOK_WRAP_CHARS = 26       # fallback only, if the font cannot be measured
HOOK_MAX_LINES = 3
HOOK_SCRIM_STRIPS = 24     # feathering resolution for the scrim gradient

HOOK_FONT_CANDIDATES = [
    os.path.normpath(os.path.join(
        BASE_DIR, "..", "selene-dreams-educational-v1.0", "fonts",
        "EKRoumald-Roman.otf")),
    os.path.normpath(os.path.join(
        BASE_DIR, "..", "selene-dreams-educational-v1.0", "fonts",
        "Inter-Variable.ttf")),
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


# ── metrics readback ───────────────────────────────────────────────────────
# (label, hours after publishing). Read ONCE per window, in order.
# Comparability is the point: a 6-hour view number and a 9-day view number
# are not the same measurement, so the lane refuses to mix them.
METRIC_WINDOWS = [
    ("72h", 72),      # the trial window has closed
    ("7d", 168),      # the tail
]

# Read metrics on the ordinary 15-minute tick rather than on their own agent.
# Cheap (a handful of GETs, only when a window is actually due) and it cannot
# fail independently of the thing it reports on.
METRICS_ON_TICK = True
METRICS_MAX_PER_TICK = 6      # bound the work one tick can do

# A window that could not be read holds no number, so it is NOT a measurement
# and must not count as one. It is retried on later ticks up to this many times
# before the lane accepts that it is not coming. Bounded so a permanently
# unreadable reel cannot retry on every tick forever.
METRICS_UNREADABLE_RETRIES = 5


# ── framing: any source ratio onto a phone screen ──────────────────────────
CANVAS_W = 1080
CANVAS_H = 1920

# Anything this close to 9:16 already is left completely alone. 0.02 covers
# 1080x1920 (0.5625) and the drone's 1728x3072, and excludes 4:3 and 16:9.
FRAMING_RATIO_TOLERANCE = 0.02

# What a non-vertical clip gets when the Videos tab says nothing.
# "fit" ON PURPOSE: a wrong crop silently destroys 72% of the frame and you
# only find out by watching the output. A wrong fit is merely less punchy.
# Unattended, the safe failure is the right default.
FRAMING_DEFAULT = "fit"

# Where the kept window sits when cropping. 0.5 = middle.
CROP_X_FRAC = 0.5

# The field behind a fitted clip. Moss Green — the brand's own "warm
# alternative to black" (brand-guide.md). Ecru hook text on it measures about
# 9:1 contrast, so a fitted hook needs no scrim at all.
FIT_FIELD_COLOUR = "#273F22"
FIT_VIDEO_Y_FRAC = 0.40         # 0 = video at the top, 1 = bottom, 0.5 centred.
                                # 0.40 lifts the footage so the hook fits below it.
FIT_HOOK_BAND_SHARE = 0.55      # how much of a field the hook may use ("above" mode)

# Where the hook sits on a FITTED clip. "below": in the lower brand field,
# starting FIT_HOOK_GAP_PX under the footage and never reaching into the strip
# Instagram covers with the caption, handle and audio line (roughly the bottom
# quarter of the screen). "above": the 1.0 behaviour, centred in the upper
# field — which on a centred 16:9 clip put the words at 8-26% of the frame,
# under Instagram's own top bar. Marcus, 2026-09-16: "way too high".
FIT_HOOK_POSITION = "below"
FIT_HOOK_GAP_PX = 40
IG_SAFE_BOTTOM_FRAC = 0.76      # nothing of ours below this line

FRAMING_CRF = 20                # the frame is re-encoded; keep it clean
