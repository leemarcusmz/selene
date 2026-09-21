# =============================================================================
# Selene Dreams — Image Generation Script v3.0
# config.py — Credentials and Settings
# =============================================================================
# IMPORTANT: Never share this file or commit it to version control.
# Keep it in your local selene-dreams-script-v3.0 folder only.
# =============================================================================

import os

# --- Base Directory (absolute path to this script's folder) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ─── Secrets come from .env (2026-08-19) ─────────────────────────────────────
# One file to rotate, one file to protect. Values were previously hardcoded
# here and quoted in prompts/logs; those copies are scrubbed. github_token.txt
# stays separate (seven scripts read it directly).
def _load_env():
    env = {}
    path = os.path.join(BASE_DIR, ".env")
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                env[k.strip()] = v.split("#")[0].strip() if " #" in v else v.strip()
    except FileNotFoundError:
        pass
    return env

_ENV = _load_env()

def _secret(key):
    val = _ENV.get(key)
    if not val:
        raise RuntimeError(
            f"Missing secret {key!r}: create {os.path.join(BASE_DIR, '.env')} "
            f"from .env.example and fill it in.")
    return val

# =============================================================================
# REPLICATE (Nano Banana Pro / Gemini 3 Pro Image)
# =============================================================================
# Sign up at https://replicate.com, then grab your token from
# https://replicate.com/account/api-tokens. Paste it below.
REPLICATE_API_TOKEN = _secret("REPLICATE_API_TOKEN")

# Model on Replicate. Nano Banana Pro is Google's Gemini 3 Pro Image model —
# stronger identity preservation and multi-reference (up to 14 images) than
# FLUX 2 Pro, at higher cost (~$0.24/image at 4K). Switched from FLUX because
# FLUX invented generic products instead of using the exact reference.
REPLICATE_MODEL = "google/nano-banana-pro"

# Output settings — used by replicate_service.py.
IMAGE_ASPECT_RATIO = "3:4"     # Closest to Instagram's preferred 4:5
IMAGE_OUTPUT_FORMAT = "png"
IMAGE_RESOLUTION = "4K"        # Nano Banana Pro accepts "1K", "2K", or "4K"
SAFETY_FILTER_LEVEL = "block_only_high"  # least strict, best for product work

# =============================================================================
# GOOGLE — Sheets and Drive
# =============================================================================

GOOGLE_SHEET_ID = "1GJO1YgfPY1QSTX-7ZhBA4xI7teKsajf04-MVPkMdp9s"
GOOGLE_SHEET_NAME = "Generation Queue"
GOOGLE_DOC_SHEET_NAME = "Documentation"

CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
OAUTH_CREDENTIALS_FILE = os.path.join(BASE_DIR, "oauth_credentials.json")
OAUTH_TOKEN_FILE = os.path.join(BASE_DIR, "token.json")

# --- Google Drive Folder IDs (10. AI Generation parent folder) ---
DRIVE_PARENT_FOLDER_ID = "15gGeETzOnyKWfoYwKAUJCxqML7T8a75I"
DRIVE_PRODUCT_PHOTOS_FOLDER_ID = "1m4WR8RLn7iyEYH6KRwPVnA3JpmZxfNVF"   # 01. Product Photos
DRIVE_REFERENCE_IMAGES_FOLDER_ID = "1aOv6xEr9CMqy4N4ON6-SSZKVjz7Sqmhn"  # 02. Reference Images
DRIVE_GENERATED_IMAGES_FOLDER_ID = "1AKFSDnS9MkAHcCYp55ocO_gP_ARDo9ZJ"  # 03. Generated Images

# --- Shared video/audio libraries (added 2026-09-09) -------------------------
# "05. Video Reel" and its two subfolders. These live HERE rather than in
# reel_config.py on purpose: Marcus restructured them so other flows can reuse
# the same source material, so any lane should be able to import them without
# depending on the trial-reel lane.
#   05. Video Reel
#     +- 01. Video Content   raw footage in, any flow may read
#     +- 02. Audio Content   licensed/owned audio only (Artlist)
DRIVE_VIDEO_REEL_FOLDER_ID = "1fWauaUr9f0NpkDA62MX6J2e9g1vht4O4"      # 05. Video Reel
DRIVE_VIDEO_CONTENT_FOLDER_ID = "1loAD7AVq9NckfMRCM_q6XeLmU4ebEqll"   # 05/01. Video Content
DRIVE_AUDIO_CONTENT_FOLDER_ID = "1LCt-bh3ZJMSQIU8d5fh4rg83xb_GdHre"   # 05/02. Audio Content

# =============================================================================
# SHEET — Column Indices (0-based)
# =============================================================================
# 16 columns total (2026-07-22: Reference Image 1-5 and the legacy Status
# column were removed — references are no longer used by generation, and the
# control status lives in the Generation Status tab col D).
# # is a formula (=ROW()-1) so each data row auto-numbers.

COL_NUMBER = 0          # A — # (auto-numbered)
COL_YEAR = 1            # B — Year
COL_MONTH = 2           # C — Month
COL_FABRIC = 3          # D — Fabric
COL_PRODUCT_TYPE = 4    # E — Product Type
COL_VARIANT = 5         # F — Variant
COL_PROMPT_1 = 6        # G — Prompt 1
COL_PROMPT_2 = 7        # H — Prompt 2
COL_PROMPT_3 = 8        # I — Prompt 3
COL_PROMPT_4 = 9        # J — Prompt 4 (kept for layout; capped at 3 prompts)
COL_PROMPT_5 = 10       # K — Prompt 5 (kept for layout; capped at 3 prompts)
COL_CREDITS = 11        # L — Credits Used
COL_OUTPUT_FOLDER = 12  # M — Output Folder
COL_IMAGE_URLS = 13     # N — Image URLs
COL_CAROUSEL_ID = 14    # O — Carousel ID
COL_NOTES = 15          # P — Notes

PROMPT_COLS = [COL_PROMPT_1, COL_PROMPT_2, COL_PROMPT_3, COL_PROMPT_4, COL_PROMPT_5]
TOTAL_COLS = 16

# =============================================================================
# STATUS VALUES
# =============================================================================

STATUS_READY = "Ready"
STATUS_HOLD = "Hold"
STATUS_PROCESSING = "Processing"
STATUS_DONE = "Done"
STATUS_ERROR = "ERROR"

# =============================================================================
# GENERATION STATUS TAB (control panel — added 2026-07-22)
# =============================================================================
# The "Generation Status" tab is the new control surface. Image generation is
# triggered from its column D (not the queue's Q anymore); errors go to
# System Remark(s) col M; completion date/time to E/F. Rows keyed by # in
# col B, matching the Generation Queue #. Queue row = # + 1.
# Layout (1-based cols): A spacer | B # | C No. of Prompts | D Status (gen) |
# E Completion Date | F Completion Time | G Status (caption) |
# H Completion Date | I Completion Time | J Post Status | K Scheduled Date |
# L Post Date | M System Remark(s) | N User Remark(s)

GS_SHEET_NAME = "Generation Status"

# Marcus's own style references (added 2026-08-26): a folder of hand-picked
# images showing the kind of content he wants. The prompt writer views the
# newest few before writing prompts. Lives OUTSIDE the versioned script
# folder so it survives v3.0 -> v4.0 upgrades.
REFERENCE_IMAGES_DIR = os.path.normpath(
    os.path.join(BASE_DIR, "..", "reference-images"))
# 2026-09-16: the local folder is now a CACHE of Drive "02. Reference Images"
# (DRIVE_REFERENCE_IMAGES_FOLDER_ID above), synced by reference_drive.py into
# style/ and educational/ subfolders. Style only — never generator input.
# 2026-09-16: "Selene Dreams - Posted Content" — ONE sheet for every published
# post across all lanes, where Marcus rates (N) and comments (O). Mirror +
# read-back in posted_sheet.py. Created in his Drive, shared to the SA.
POSTED_SHEET_ID = "19evO6rmh-O9jMmQVUqu0ctV8Z9RRXArFt2xyP6i0bfE"
POSTED_MANUAL_WALK = 50                # hand-posted items pulled from the account
REFERENCE_MAX_VIEW = 6                 # images a writer is asked to view
REFERENCE_MAX_DESCRIBE_PER_RUN = 8     # vision notes written per sync

GS_HEADER_ROW = 3           # column-title row ("#" in col B)
GS_FIRST_DATA_ROW = 4       # GS row for # N = N + 3

GS_COL_NUMBER = 2           # B
GS_COL_NUM_PROMPTS = 3      # C
GS_COL_GEN_STATUS = 4       # D
GS_COL_GEN_DATE = 5         # E
GS_COL_GEN_TIME = 6         # F
GS_COL_CAP_STATUS = 7       # G
GS_COL_CAP_DATE = 8         # H
GS_COL_CAP_TIME = 9         # I
GS_COL_POST_STATUS = 10     # J
GS_COL_SCHED_DATE = 11      # K
GS_COL_POST_DATE = 12       # L
GS_COL_SYS_REMARK = 13      # M
GS_COL_USER_REMARK = 14     # N
GS_COL_POST_URL = 15        # O — paste the live Instagram URL here after posting.
# That single paste is what closes the learning loop: outcomes_runner.py uses
# it to match the scraped performance of a real post back to the queue row,
# prompt, QA score and caption that produced it. Without it the pipeline can
# only ever learn what looks right, never what worked.

# =============================================================================
# APIFY — two tokens, deliberately separate (2026-08-19):
#   APIFY_TOKEN      read-only, scoped to the three saved scrape tasks. The
#                    weekly research GETs use this. Cannot run actors.
#   APIFY_RUN_TOKEN  account-level Actors Read+Run ("Selene actor runs").
#                    Used ONLY where an actor must be started: comment mining
#                    and repair_slides. Created after the read-only token's
#                    scoped edits refused to grant Run (403 on every attempt).
APIFY_RUN_TOKEN = _secret("APIFY_RUN_TOKEN")

# APIFY (read-only — weekly scrape datasets)
# =============================================================================
# Used by outcomes_runner.py to read Selene's own scraped post metrics. The
# weekly research agent uses the same token via weekly_research_prompt.md.
APIFY_TOKEN = _secret("APIFY_TOKEN")
APIFY_POSTS_TASK = "kpVx7oSv8EPBUWhCT"
OWN_IG_USERNAME = "selenedreams_official"

# Caption statuses (col G)
CAP_STATUS_NOT_AVAILABLE = "Not Available"
CAP_STATUS_NOT_STARTED = "Not Started"
CAP_STATUS_READY = "Ready"
CAP_STATUS_PROCESSING = "Processing"   # transient — set by caption_runner while working
CAP_STATUS_ERROR = "ERROR"
CAP_STATUS_DONE = "Done"

# =============================================================================
# AGENT MODEL ROUTING (added 2026-08-12)
# =============================================================================
# Each stage gets the model and reasoning effort it actually needs, instead of
# every agent inheriting the same default. Values are Claude Code aliases
# (fable / opus / sonnet / haiku) and effort levels (low / medium / high /
# xhigh / max). Set model to None to inherit the CLI default.
#
# The reasoning behind these defaults:
#   - Sonnet is the workhorse. These tasks are well-specified — an explicit
#     12-point rubric, a locked caption format, a fixed prompt structure —
#     which is exactly the shape of work where Sonnet lands closest to
#     frontier quality, at a fraction of Fable's token cost.
#   - The CRITIC gets Opus. It is the one genuinely adversarial task, its
#     context is small (a report plus data lines), and a critic that misses
#     an unsupported claim defeats its own purpose. Cheap place to spend.
#   - QA runs at medium effort. Scoring images against a rubric you were
#     handed is recognition, not deliberation.
#   - Fable is deliberately unused: it is built for the hardest, longest
#     open-ended work, and every stage here is bounded and well-specified.

STAGE_MODELS = {
    "default":        {"model": "sonnet", "effort": "high"},
    "research":       {"model": "sonnet", "effort": "high"},
    "critic":         {"model": "opus",   "effort": "high"},
    "screening":      {"model": "sonnet", "effort": "high"},
    "prompts":        {"model": "sonnet", "effort": "high"},
    "caption":        {"model": "sonnet", "effort": "high"},
    "caption_review": {"model": "sonnet", "effort": "high"},
    "qa":             {"model": "sonnet", "effort": "medium"},
    "eval":           {"model": "sonnet", "effort": "high"},
}

# =============================================================================
# AESTHETIC AUTHORITY (added 2026-08-12)
# =============================================================================
# When True, the prompt runner reads brand-guide.md and treats it as governing
# the look of generated images — the same authority every other stage already
# grants it. Until now the prompt runner was the ONLY stage that never read
# the brand guide, which is the real reason generated images stayed indoor
# japandi while the screener judged references against the deck's world of
# bedding outdoors at dusk.
#
# SETTING THIS TRUE CHANGES WHAT THE PIPELINE PRODUCES. Set it False to keep
# the previous hardcoded aesthetic (indoor japandi, no people).
BRAND_GUIDE_GOVERNS_PROMPTS = True

# =============================================================================
# CREDITS / COST TRACKING
# =============================================================================
# Replicate bills per image; tracking a flat cost-per-image makes the sheet
# show approximate $ spent per row. Update if Replicate's pricing changes.
# Nano Banana Pro at 4K is roughly $0.24/image on Replicate.
COST_PER_IMAGE_USD = 0.24

# =============================================================================
# WEBHOOK
# =============================================================================

WEBHOOK_SECRET = _secret("WEBHOOK_SECRET")
WEBHOOK_PORT = 5001
