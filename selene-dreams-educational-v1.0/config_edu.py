# =============================================================================
# config_edu.py — Selene Educational Carousel flow configuration
# VERSION 1.12 — 2026-09-14
# CHANGELOG
#   1.12 2026-09-14  EDU_NOTIFY_PER_POST: the per-post 'Final look' mail is
#                    off. The review page (review.gs v2.1) now shows educational
#                    carousels beside the AI ones and is the single gate, so a
#                    second mail per post is noise. notify_edu still builds the
#                    strip, uploads it to Drive and sets K=Review - only the
#                    send is skipped. Flip this back to True to restore it.
#                    NOTE: 1.11 was stamped on 2026-09-14 with no changelog
#                    line; whatever it changed is undocumented.
#   1.10 2026-09-11  TAG_PER_TICK: how many undescribed library images one tick
#                    describes (one vision call per 10).
#   1.9  2026-09-11  MAIL_TO -> selenedreams.admin@gmail.com (brand inbox, sender
#                    is the same account via a Gmail app password).
#   1.8  2026-09-10  IMAGE_LIBRARY_SHEET_ID: the Image Library and Sources tabs
#                    moved to their own spreadsheet, "Selene Dreams — Image
#                    Library", so other flows can share it.
#   1.7  2026-09-10  GEN_CANDIDATES_COVER / _INTERIOR for the candidate picker
#                    (render_runner v1.4): two rolls for the cover, one for an
#                    interior, reroll only on rejection.
#   1.6  2026-09-10  PICK_MIN_CONFIDENCE for the picker call (plan_edu v2.0).
#   1.5  2026-09-10  Slide-level image matching settings: REUSE_MIN_SCORE (below
#                    it a slide generates from its own words) and NON_BRAND_TAGS
#                    (library images that can never stand in for Selene bedding).
#   1.4  2026-09-09  ARM_PER_TICK. Marcus approved all seven queued rows at once;
#                    the arm stage would have flipped all seven to Ready in one
#                    tick, meaning seven concurrent renders and seven `claude -p`
#                    caption calls on the first-ever live run of stages 4-6,
#                    against a Sheets quota that has already thrown 429s under
#                    lighter load. The cap keeps every approval — they just move
#                    through the chain one per tick instead of in a burst.
#   1.3  2026-09-09  Behind Selene added to PARKED_TYPES — Marcus retired
#                    founding-story content outright.
#   1.2  2026-09-09  Image-sourcing settings: PARKED_TYPES (Inspirational is TBD),
#                    the reuse variety rule (no two slides from the same shoot),
#                    and the reroll loop's settings.
#   1.1  2026-09-09  FULL FLOW. Adds everything the writer, caption, notify and
#                    publish stages need: V3_DIR on sys.path so the proven v3.0
#                    modules (claude_client, image_host, publish primitives,
#                    caption validator) are IMPORTED, never copied; the fixed
#                    Thursday slot; mail settings; the verified-claims file;
#                    the Post-Status vocabulary for col K. Nothing here changes
#                    v3.0 - it is read-only from this side.
#   1.0  2026-08-28  First release. Brand-new flow, independent of v3.0:
#                    own sheet, own server (port 5002), poll-based (no ngrok).
#                    Reads the v3.0 .env for API tokens (single source of truth).
# =============================================================================
import os

EDU_DIR = os.path.dirname(os.path.abspath(__file__))
V3_DIR = os.path.join(os.path.dirname(EDU_DIR), "selene-dreams-script-v3.0")

# --- credentials (referenced from v3.0 — never copied) -----------------------
CREDENTIALS_PATH = os.path.join(V3_DIR, "credentials.json")
ENV_PATH = os.path.join(V3_DIR, ".env")

def load_env():
    env = {}
    try:
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env

# --- sheets ------------------------------------------------------------------
EDU_QUEUE_SHEET_ID = "1DoOtov9T1A7qqJvPy-IhJC8OzQjweM0PdpOC_jJ8hEw"   # Educational Content Generation Queue
POST_TOPIC_SHEET_ID = "19P9XsWrwGye1vPr3iw5CRmIPzChUo3RuqHA6ZA2NLeE"  # Post Topic (topics + slide text)

TAB_QUEUE = "Generation Queue"
TAB_STATUS = "Generation Status"
# The Image Library is BRAND content, shared with other flows, so it lives in
# its own spreadsheet (Marcus, 2026-09-10). sheets_edu routes these two tab
# names there; every caller still says S.tab(C.TAB_LIBRARY).
IMAGE_LIBRARY_SHEET_ID = "15V_5bFM4z0_t7CPP2PZAtnFhy5SIoNHBow4DqphnloI"   # Selene Dreams — Image Library
TAB_LIBRARY = "Image Library"
TAB_SOURCES = "Sources"          # one row per Drive folder: Ours? / Product / date
# Drive roots the indexer walks. Every folder listed on the Sources tab is
# walked too; this is only the default for the v3.0 lane's back catalogue.
LIBRARY_ROOTS = ["03. Generated Images"]
TAG_PER_TICK = 10                # undescribed images described per tick (1 vision call)
TAB_CAPTION = "Generated Caption"
TAB_TOPICS = "Topics"

STATUS_HEADER_ROW = 3   # Generation Status: header row 3, data from row 4

# --- drive -------------------------------------------------------------------
# 03. Generated Images lives in Drive; the indexer walks it for the Image Library.
GENERATED_IMAGES_FOLDER_NAME = "03. Generated Images"
EDU_OUTPUT_SUBFOLDER = "Educational"   # rendered slides: .../03. Generated Images/Educational/Row {n}/

# --- image generation --------------------------------------------------------
REPLICATE_MODEL = "google/nano-banana-pro"   # same family the v3.0 flow uses; change here only
MAX_GEN_RETRIES = 4                          # capacity backoff, mirrors v3.0 lesson
GEN_RETRY_WAITS = [30, 120, 300, 600]

# --- canvas ------------------------------------------------------------------
CANVAS_W, CANVAS_H = 1080, 1350   # IG portrait, brand grid: 5-col, 70px margins
MARGIN = 70
CORNER_RADIUS = 15                # brand rule: always 15

# --- palette (brand guidelines p.8-9) ---------------------------------------
MOSS = "#273F22"; ECRU = "#E8E4D8"; WINTER = "#F5F3EF"
SAGE = "#7C896F"; ROSE = "#F7D4BD"
FLAT_BACKGROUNDS = [ECRU, WINTER, ROSE]   # light tier only behind long text

# --- fonts -------------------------------------------------------------------
FONT_DIR = os.path.join(EDU_DIR, "fonts")
ROUMALD_BOLD = os.path.join(FONT_DIR, "EKRoumald-Bold.otf")
ROUMALD_ROMAN = os.path.join(FONT_DIR, "EKRoumald-Roman.otf")
ROUMALD_ITALIC = os.path.join(FONT_DIR, "EKRoumald-Italic.otf")
INTER_VARIABLE = os.path.join(FONT_DIR, "Inter-Variable.ttf")

# --- rules -------------------------------------------------------------------
MAX_SLIDES = 7
INSPIRATIONAL_MAX_SLIDES = 4
SERVER_PORT = 5002

# Shared secret for /tick and /publish (edu_server v2.5+). Same value the
# v3.0 server uses — read from the same .env, which is the single source of
# truth for this lane's secrets. Empty means the .env is missing or has no
# WEBHOOK_SECRET line; edu_server refuses every request in that case rather
# than falling open.
WEBHOOK_SECRET = load_env().get("WEBHOOK_SECRET", "")

LOG_PATH = os.path.join(EDU_DIR, "_logs", "edu.log")
STATE_PATH = os.path.join(EDU_DIR, "_state", "edu_state.json")

# =============================================================================
# v1.1 — the full flow
# =============================================================================
import sys as _sys
if V3_DIR not in _sys.path:
    _sys.path.insert(0, V3_DIR)     # import v3.0's claude_client / image_host / publish_runner

PROMPT_DIR = os.path.join(EDU_DIR, "prompts")
CLAIMS_PATH = os.path.join(PROMPT_DIR, "claims_edu.md")   # the ONLY product facts copy may state

# --- writer -----------------------------------------------------------------
WRITER_MAX_ROUNDS = 2            # rewrite rounds when copy busts a cap, then flag
WRITER_TIMEOUT = 480

# --- caption ----------------------------------------------------------------
SITE_URL = "selenedreams.com"    # the ONLY shop pointer on an educational post (Marcus: caption only)
CAPTION_TIMEOUT = 600

# --- notify (final look) ----------------------------------------------------
# Gmail SMTP with an APP PASSWORD (Google Account > Security > App passwords).
# Both come from the v3.0 .env so secrets stay in one file:
#   SELENE_MAIL_FROM=you@gmail.com
#   SELENE_MAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
# If either is missing the strip is still saved to Drive and the row is marked
# "Review" - the pipeline never stalls on mail.
MAIL_TO = "selenedreams.admin@gmail.com"   # Marcus 2026-09-11: brand inbox, not personal
# The review page is the single human gate for BOTH lanes as of 2026-09-14, so
# the per-post "Final look" mail is off. The strip is still built, still saved
# to Drive, and K still becomes Review - the row simply waits on the page
# instead of on an inbox. True restores the old one-mail-per-post behaviour.
EDU_NOTIFY_PER_POST = False
SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 465

# --- publish ----------------------------------------------------------------
# Fixed day, Marcus's call (2026-09-09): educational takes THURSDAY, the image
# lane keeps Tue/Sat. Chosen on benchmark grounds (mid-week, splits the other
# two evenly) - NOT on Selene's own engagement data, which is not yet collected
# for own posts. Revisit once the outcomes loop exists.
POST_WEEKDAY = 3                 # Mon=0 ... Thu=3
POST_HOUR = 21                   # 21:00, same hour as the image lane
POST_TZ_NAME = "America/New_York"
PUBLIC_REPO_PREFIX = "posts/edu" # slides hosted at posts/edu/<week>/row<N>_slide<i>.jpg
PRODUCT_TAGS = False             # Marcus: caption only, no shop tags on teaching posts

# --- Post-Status vocabulary (Generation Status col K) ------------------------
POST_REVIEW = "Review"           # strip emailed, waiting for Marcus's eye
POST_APPROVED = "Approved"       # Marcus flips this from his phone
POST_SCHEDULED = "Scheduled"     # runner set L (date); change K to anything else to cancel
POST_POSTED = "Posted"
POST_HOLD = "Hold"               # a failure parked here; error in col N

# --- topic types that are parked ---------------------------------------------
# Marcus 2026-09-09: Inspirational's shape and image sourcing are both undecided.
# writer_edu and plan_edu both skip these outright.
# Inspirational: shape and image sourcing undecided (Marcus 2026-09-09).
# Behind Selene: RETIRED 2026-09-09 — Marcus does not want founding-story or
# brand-history content. Every slide of that kind rests on claims about the
# family and the company that are not on selenedreams.com and that nothing in
# the pipeline can check.
PARKED_TYPES = {"Inspirational", "Behind Selene"}

# --- reuse variety ------------------------------------------------------------
# The library's "subject" column is the Drive PATH, so consecutive least-used
# picks came from the same shoot folder ("Row 22", "Row 23") and a linen-vs-percale
# post got six shots of the same sheet set. A slide may not reuse an image from a
# shoot already used in the same post.
REUSE_ONE_PER_SHOOT = True

# A library image is reused for a slide only when its tags score at least this
# against the slide's own words (2 per slide word, 1 per topic-type word).
# Below it the slide GENERATES from a prompt written from the slide copy, so the
# picture says what the bubble says. Raise for stricter matching / more gens.
REUSE_MIN_SCORE = 3

# The picker (one Claude call per post, plan_edu v2.0) must be at least this
# confident that a library image illustrates the slide's brief; below it the
# slide generates. 0.6 = "a reader would see the words in the picture".
PICK_MIN_CONFIDENCE = 0.6

# How many images a GEN slide rolls before Marcus sees it. The cover carries the
# brand judgement, an interior sits under a text bubble. Every candidate is kept
# (Drive Row folder + Image Library), so a second roll is never thrown away.
GEN_CANDIDATES_COVER = 2
GEN_CANDIDATES_INTERIOR = 1

# Tags that mark an image as NOT Selene bedding, whatever else it scores.
# The library is the v3.0 lane's back catalogue, and some of it shows product
# types Selene does not sell. Marcus, #16: "doesn't even look like ours".
NON_BRAND_TAGS = ("quilt", "quilted", "comforter", "stripe", "striped", "plaid",
                  "pattern", "patterned", "velvet", "knit", "fleece", "flannel",
                  "sofa", "couch", "armchair")

# --- throughput ---------------------------------------------------------------
# How many Approved rows the arm stage may flip to Ready in one tick.
# 1 = strictly sequential: one carousel renders, captions and emails per tick,
# so a failure anywhere in stages 4-6 costs one post, not the whole batch, and
# the Sheets read quota never sees seven rows of traffic at once.
# Raise it once the chain has run clean end to end a few times.
ARM_PER_TICK = 1

# --- reroll -------------------------------------------------------------------
# Marcus's call 2026-09-09: generate first, show him the prompt actually used,
# he comments, the comment plus the ORIGINAL prompt produce a revised prompt and
# only that slide regenerates. Feedback goes in Generation Status col O
# (User Remark(s)) as: reroll <slide#>: <what he wants different>
REROLL_PATTERN = r"reroll\s+(\d+)\s*:\s*([^|]+)"
REROLL_TIMEOUT = 300
