# Trial Reel Lane — build notes and handoff

**VERSION 2.6 — 2026-09-16**

## Changelog
- **2.6 — 2026-09-16** THE TASTE LAYER rides this tick. Marcus's decision: keep
  the three flows separate, make what they learn shared. Two new modules in
  v3.0, both hosted on this tick because it is the always-on process with the
  IG token: `post_metrics.py` reads CAROUSEL results back (image + educational
  lanes, same 72h/7d windows as reels, into `_state/post-metrics.json`), and
  `taste_store.py` regenerates `taste/{references,feedback,outcomes}.md` in the
  selene-ig-memory repo from all three lanes and pushes, at most every 6h.
  Both fail-open; a failure cannot touch a publish. `--taste`, `--post-metrics`.
  The distill step (taste/brief.md, injected into every writer) is the NEXT
  build; until then the raw files accumulate.
- **2.5 — 2026-09-16** FEEDBACK LOOP (`reel_feedback.py`). Marcus asked where
  to leave comments so the lane learns. Answer: the sheet he already opens.
  On the Trial Reels tab, **Q Notes** and the new **W Rating (1-5)** on any
  published row; plus a new **Taste Notes** tab for directions not tied to a
  post. Every tick reads both (fail-open, like the control tab), keeps them in
  `reels.json`, regenerates `00. Social Media Posts/reel-taste.md`, and hands
  the block to the hook and caption writers (prompts v4). A pattern rated
  <= 2.0 over >= 2 ratings leaves the **rotation**. THE RULE: feedback changes
  HOW a reel is written, never WHETHER it publishes — no approval gate has
  been added by the back door. `--feedback` shows what the writers see.
  Re-run `setup_reel_sheet.py` once to add column W and the tab.
- **2.4 — 2026-09-11** DRIVE SUBFOLDERS ARE NOW SEARCHED. `reel_drive` only
  ever listed direct children of `01. Video Content`, so organising footage into
  `_New Zealand Shoot / _Horizontal` made every clip invisible to the lane — and
  it reported an empty pool, which reads as "nothing new" rather than "I cannot
  see your files". Now walks 3 folders deep and records which subfolder each
  clip came from. Also adds `reframe_prep.py`, which builds contact sheets of
  horizontal footage with candidate 9:16 crop windows drawn on, so the crop is
  chosen by looking rather than guessing.
- **2.3 — 2026-09-11** THE CONTROL TAB NOW ACTUALLY CONTROLS MUSIC.
  `reel_music.maybe_add` re-ran its own silence test and overrode the caller,
  so `Audio in video? = no` was silently ignored on any clip with faint audio —
  wind on drone footage, room tone. The sheet said "-> Music: yes", the log said
  "leaving it alone", and the reel published with the noise. The decision is now
  made once in `reel_runner` and passed down. Also documented: adding music
  REPLACES the clip's own audio, it does not layer under it.
- **2.2 — 2026-09-11** ANSWERED: **trial reels DO expose `/insights`**, full
  metric set — views, reach, likes, comments, shares, saves, average watch time,
  total watch time. The negotiation found all nine on the first try and cached
  them. Three fixes came out of that first live run: `--metrics-now` no longer
  fills real windows with an off-schedule reading (it takes a **probe** instead,
  which blocks nothing); an **unreadable** window is now retried rather than
  counting as read; and `--repair-windows` undoes the damage the first version
  did. Sheet 2.2 labels a probe as `probe @45h` so it can never be mistaken for
  a measurement.
- **2.1 — 2026-09-10** METRICS READBACK. `reel_metrics.py` reads Instagram
  results back at **72h** and **7d** per reel and writes them into the sheet.
  `--variants` now prints real views. Two things it does NOT do: invent zeros
  when a metric is unreadable (it stamps "unreadable" instead, because "0 views"
  and "cannot see views" lead to opposite conclusions), and assume trial reels
  expose `/insights` at all — it negotiates the metric set against your own
  media and caches the answer. Also fixes a `NameError` in `--status` that had
  been shipped and never run.
- **2.0 — 2026-09-10** OVERLAY NO LONGER USES ffmpeg's `drawtext`. The first
  overlay run failed with "No such filter: 'drawtext'" — the Mac's ffmpeg was
  built without libfreetype. Text and scrim are now drawn with Pillow into one
  transparent PNG and composited with `overlay`, which every ffmpeg build has.
  Side benefits: a real gradient scrim, and wrapping measured against the actual
  font instead of a 26-character guess.
- **1.9 — 2026-09-09** Drive restructured: `05. Video Reel` with subfolders
  `01. Video Content` and `02. Audio Content`, replacing `05. Trial Reel Videos`
  and `06. Reel Music`. Folder ids moved to the SHARED `config.py` so other
  flows can reuse the same footage and audio.
- **1.8 — 2026-09-09** CONTROL TAB. A "Videos" tab in the sheet decides overlay
  and music per video: no on-screen text → always overlay; text already there →
  never; no audible audio → add a licensed track; audio there → leave it. Rows
  are added automatically, pre-filled from detection. Also `reel_music` (Drive
  audio folder, empty = silent as before) and loudness-based silence
  detection. FIRST LIVE PUBLISH: instagram.com/reel/DdEElE-jrbD/
- **1.7 — 2026-09-09** FILENAME PRODUCT DECLARATION. Name the product in the
  Drive filename and the lane treats it as ground truth, overriding the vision
  pass. Renaming in Drive now propagates without a re-download.
- **1.6 — 2026-09-09** DELIVERY DOWNSCALE. The first real video was a 48.5 MB
  drone master (1728x3072, 35 Mbps, 11s) — a 64.7 MB base64 PUT to GitHub for a
  clip Instagram would transcode to 1080x1920 anyway. `video_host` v1.1 now
  re-encodes anything wider than 1080 or fatter than 12 Mbps before hosting.
- **1.5 — 2026-09-09** "UNCLEAR PRODUCT" NOW PROPAGATES. The first real dry run
  found three linked bugs with one root cause — the vision pass honestly said
  the product was unclear and nothing downstream listened. `Meet the Product` is
  now ineligible when the product is unclear, product nouns in hashtags are
  rejected in that case, and the hook prompt (v2) carries a worked example of
  the literal-description failure.
- **1.4 — 2026-09-09** DRIVE INTAKE. Videos now come from the Drive folder
  `05. Video Reel / 01. Video Content`, so they can be added from a
  phone. Downloads feed the same local pool, so nothing downstream changed.
- **1.3 — 2026-09-09** Sheet moved into Drive `Selene Bedding / 10. AI Generation`
  alongside the other queue sheets, and recreated by CSV import so the header
  row exists already. New file id. `setup_reel_sheet.py` now renames the
  imported tab rather than adding a second one.
- **1.2 — 2026-09-09** SHEET MIRROR. Every published trial reel is appended to
  the "Selene Dreams - Trial Reel" sheet — hook, caption, video, pattern, mode.
  One-way and fail-open; `reels.json` is still the only source of truth.
- **1.1 — 2026-09-09** HOOK VARIANTS. A source video is now a parent yielding up
  to 3 runs, each with a different hook, so run-over-run comparison is built in.
  Two application modes (caption / overlay) with caption as the evidence-backed
  default. Adds the hook bank, `hook_overlay.py` with luminance-measured
  legibility, `--variants`.
- **1.0 — 2026-09-09** First build. Drop-folder autopilot publishing Instagram
  trial reels with no approval step. Resolves the reel caption routing deferred
  on 2026-09-07.

---

## What you do

**Upload a video to Google Drive:**
`My Drive / Selene Bedding / 10. AI Generation / 05. Video Reel / 01. Video Content`
https://drive.google.com/drive/folders/1loAD7AVq9NckfMRCM_q6XeLmU4ebEqll

That is the whole job, and it works from your phone. Within 15 minutes the lane
downloads it and it joins the pool.

Dropping a file straight into `03. Content/04. Trial Reels/00. Drop Here/` still
works too — that folder is now a local cache rather than the source.

### Name the product in the filename
The vision pass often cannot identify a product from frames — a crinkled beige
cloth on a sofa is genuinely ambiguous. When it can't, the lane refuses to name
a product, drops the `Meet the Product` style, and blocks product hashtags.

**Put the product in the Drive filename and that all comes back.** Renaming in
Drive is two taps on a phone.

```
DJI_20250705172022_0090_D_1.MP4     -> stays "unclear"
Gauze_Blanket_sofa-shake.MP4        -> Gauze Blanket
Gauze_Blanket_Soft-Maple.MP4        -> Gauze Blanket in Soft Maple
linen duvet set desert sand.mov     -> Linen Duvet Set in Desert Sand
```

Spaces, underscores and hyphens all work. It needs **both** a fabric and a
product type — `linen.mp4` and `blanket.mp4` declare nothing — and it rejects
combinations you don't sell, so `Silk_Blanket` is ignored rather than believed.

Fabrics: Linen · Gauze · Cooling · Silk · Tencel · Sateen · Percale
Types: Duvet Set · Sheet Set · Blanket · Pillow Case · Eye Mask

Renaming works **after** upload too — the stored title refreshes on the next
sync, no re-download, and the cached description is reused.

### The Drive structure
```
10. AI Generation /
  05. Video Reel /
    01. Video Content    <- upload footage here
    02. Audio Content    <- licensed/owned audio only
```
Both folder ids live in the SHARED `config.py`
(`DRIVE_VIDEO_CONTENT_FOLDER_ID`, `DRIVE_AUDIO_CONTENT_FOLDER_ID`), not in
`reel_config.py`, so any other lane can read the same material without importing
the trial-reel lane.

### How the two relate
Drive is the source; the local folder is where downloads land and where the rest
of the pipeline reads from. That means:

- A **Drive outage cannot stop** videos already in the pool from publishing.
- A video is downloaded **once** and reused across all its hook variants.
- Deleting a file from the local pool does **not** trigger a re-download — the
  lane treats that as you removing it on purpose.
- Files over 90 MB are skipped with one log line, said once, not every tick.

## What you still do by hand

**Graduating.** `graduation_strategy` is `MANUAL`, so a trial never reaches your
followers unless you pick it in the app after seeing its numbers. This was
deliberate: `SS_PERFORMANCE` would let Instagram push a video you never chose to
your real audience.

---

## The Videos control tab

Second tab in the same sheet. **One row per source video, added automatically**
the first time the lane sees one, pre-filled from what it detected — so the
normal case needs no editing.

Two columns are yours:

| Cell | Effect |
|---|---|
| **Text in video?** `no` | the hook is **burned onto** the video |
| **Text in video?** `yes` | no overlay; the hook opens the caption |
| **Audio in video?** `no` | a licensed track from `02. Audio Content` is mixed in |
| **Audio in video?** `yes` | your audio is left completely alone |
| either left **blank** | the lane decides for itself |

Your answers are written once and **never overwritten** by a later run.

### It is an OPTIONAL input, not a dependency
The lane detects both signals on its own — the vision pass reports on-screen
text, `video_host.is_effectively_silent` measures actual loudness. Your override
wins **when the sheet is readable and you've set one**. Sheet down, row missing,
cell blank → detection decides and the reel publishes anyway.

That matters: this lane was built with no sheet precisely so a Google outage
couldn't stop it, which is the failure that has twice silently stopped the
carousel lane. `reels.json` is still the only source of truth for what has
posted, what is on cooldown, and which variant is next.

## Music

Drive: `10. AI Generation / 05. Video Reel / 02. Audio Content`
https://drive.google.com/drive/folders/1LCt-bh3ZJMSQIU8d5fh4rg83xb_GdHre

**Empty folder = reels publish silent, exactly as before.** Drop tracks in and
the lane starts using them on the next tick. No flag to set.

- Only added when the clip has **nothing audible**. Real location sound is never
  overwritten.
- Normalised to −14 LUFS with a 1.2s fade out; looped if shorter than the clip.
- Least-recently-used rotation, so the account doesn't sound repetitive.
**33 Artlist tracks are synced** (222 MB in `_state/reel-music/`) as of
2026-09-11.

**Music REPLACES the clip's own audio — it does not mix under it.** The ffmpeg
call maps the video stream and the new track only. That is deliberate: the case
for adding music is a clip whose own audio is wind or handling noise, and
layering a track over wind gives you both.

**Audio format: MP3.** It is re-encoded to AAC on mixing and transcoded again by
Instagram, and every track is loudness-normalised to −14 LUFS first, so WAV's
extra fidelity is discarded three times over — at roughly 4x the file size,
re-downloaded from Drive on every sync.

- **Only licensed or owned audio belongs there.** Artlist is already connected
  for this brand. Instagram-library music cannot be attached through the API and
  ripping it is a rights problem, not a technical one — the lane cannot tell the
  difference, so the folder's contents are your warranty.

## The Trial Reel sheet

**https://docs.google.com/spreadsheets/d/1HKg5YiC_vRFKtsbo2KleH5KXxCaWgWsqyvDhETdhuEQ/edit**

Lives in `My Drive / Selene Bedding / 10. AI Generation`, the same folder as the
other queue sheets (it is `config.DRIVE_PARENT_FOLDER_ID`).

One row per published trial reel: `# · Published · Video · Variant · Hook ·
Hook pattern · Evidence · Mode · Overlay · Caption style · Caption · Hashtags ·
Permalink · Views · Likes · Comments · Notes · Reach · Shares · Saves ·
Avg watch (s) · Metrics read · Rating`.

**It is a MIRROR, not a source of truth.** `_state/reels.json` still decides
what has posted, what is on cooldown, and which hook comes next. Nothing in the
sheet is ever read back to make a decision. That is deliberate: this lane was
built with no sheet precisely so a Google outage could not stop it publishing —
the same failure that has silently stopped the carousel lane twice — and adding
visibility must not undo that. Writes are **fail-open**: if the sheet is
unreachable the reel still publishes and the row is simply missing.

**Column Q (Notes) and column W (Rating, 1-5) are yours** and are never
written by anything — but as of v2.5 they are READ. See "Telling it what you
think" below. As of v2.1
Views/Likes/Comments (N-P) and Reach/Shares/Saves/Watch/Read (R-V) are filled in
by the metrics readback — a cell is only ever written when there is a real
number for it, so anything you typed by hand survives until a reading replaces
it.

The column order is deliberately odd: the metrics jump over Q rather than
grouping together. Grouping them would move the Notes column, and `--rebuild`
restores manual cells *by position* — so tidying the header would silently shift
every note you have written one column to the left. An ugly header row is
cheaper than losing your writing.

- Backfill or repair every row from state: `python3 reel_sheet.py --rebuild`
- The sheet is owned by **you**, shared to the service account as writer. That
  order matters: a sheet created *by* a service account is owned by it, lives in
  a Drive nobody can browse, and never appears in your Drive.

## Telling it what you think (v2.5)

Two places, both in the sheet above, both usable from your phone:

1. **On a published reel's row** — type in **Q Notes** ("too poetic", "this
   one, more of this") and/or pick **W Rating** (5 = exactly right, 1 = wrong).
   The row already carries the hook, pattern, style and mode, so the note has
   its context without you typing any of it.
2. **Taste Notes tab** — directions not tied to a post: `Date | Note |
   Applies to | Seen`. "captions shorter", "more hands in frame". `Applies to`
   blank or `all` = every lane; `reels` / `images` / `educational` scopes it.
   The lane stamps **Seen** when it has read the row, so you know it landed.

What happens next, every 15-minute tick:
- both are read (fail-open: sheet down = the writers get the LAST feedback
  read, and the reel still publishes);
- kept in `_state/reels.json` under `feedback`;
- `00. Social Media Posts/reel-taste.md` is regenerated so you can read
  exactly what the writers are being told;
- the block goes into both writer prompts as "WHAT MARCUS HAS SAID ABOUT
  EARLIER REELS";
- a hook pattern averaging <= 2.0 over at least 2 ratings is dropped from the
  rotation (if that would leave nothing, they all come back).

**The rule, written into the code:** feedback changes HOW a reel is written.
It never decides WHETHER one publishes. This lane has no approval step by
your request and the taste file must not become one.

Clearing a note or rating in the sheet withdraws it. Check what the writers
currently see: `python3 reel_runner.py --feedback`.

## Turning it on (once)

0. ~~**Build the sheet's tab and formatting**~~ — **DONE 2026-09-09.**
   `python3 setup_reel_sheet.py` ran clean: tab renamed, 17 headers written,
   formatting applied. Re-run any time; it never deletes a row.

1. Restart **Start Selene AI** — server.py went 3.5 → 3.6 and the `/reel`
   route does not exist until it reboots.
2. Double-click `install_reel_agent.command` in the v3.0 folder. It runs the
   dependency check first, then installs `com.selene.reel` (a 15-minute poke,
   same shape as `com.selene.publish`).

Before either, run the check on its own:

```
cd ~/Desktop/_Claud/Work\ Projects/Selene\ Dreams/AI\ Generation\ Flow/selene-dreams-script-v3.0
python3 reel_runner.py --doctor
```

**`ffmpeg` and `ffprobe` are a new dependency and are UNVERIFIED on your Mac** —
they could not be checked from here. If `--doctor` reports them missing:
`brew install ffmpeg`.

---

## Hook variants

Each source video yields up to **3 runs, each with a different hook**. The hook
is the only thing that changes between runs, which is what makes the comparison
mean anything.

### Two modes
- **`caption`** — the hook is the caption's first line. Video untouched.
- **`overlay`** — the hook is burned onto the opening seconds.

**Default is `caption`, on evidence.** On 2026-09-09 I opened the four
highest-engagement bedding reels in the corpus (Brooklinen x3, Parachute x1).
**None of them burns a text hook onto the video.** Parachute's 19.1%-engagement
reel is pure product footage with no text at all. The category's hook lives in
the caption's first line and the opening visual.

`HOOK_MODE_ROTATION = ["caption", "caption", "overlay"]` so overlay still gets
sampled as the challenger. It is worth testing precisely because nobody in the
category does it. Set `HOOK_ROTATE = False` to lock to one mode.

### Where the hooks come from
`03. Content/00. Social Media Posts/hook-bank-v1.0.md` — six patterns, each
carrying its provenance and an evidence strength (STRONG / MEDIUM / WEAK / OURS).
**Structures, never lines.** The writer is instructed to rewrite anything that
could be mistaken for a competitor's copy.

Strongest pattern in the bank is Brooklinen's, found 4 times in the top
engagement band: a named person, a short declarative, then a flat product line
("Alana has a type. She has the best sheets ever."). It is gated behind
`has_people` — it needs a real person, and the lane will not invent a customer.

### Two data-quality rules learned while building this
1. **Rank by engagement rate, not views.** Quince: 19,205 median views at 1.99%.
   Brooklinen: 5,100 at 5.70%. Quince's counts look amplified; for organic trial
   reels Brooklinen and Parachute are the better models.
2. **Exclude giveaways.** The two highest engagement rates in the whole corpus
   were "tag 3 friends" giveaways with 1.9K comments. They teach nothing.

### Legibility — the bug this lane does NOT repeat
`selene-edu-template-kit` still has PALE PHOTOS BREAK THE TYPE open: winter-white
text, no scrim, weak veil. Selene shoots white linen in daylight, so that is the
normal case, not an edge case. Video is worse — brightness shifts shot to shot.

`hook_overlay.py` therefore **measures instead of assuming**: it samples the
luminance of the exact band the text will occupy, across the whole overlay
window, and picks the lightest treatment that clears a 4.5:1 contrast ratio
against the **brightest** sample, not the average. Escalating: ink with no scrim,
then winter white with no scrim, then a **feathered** gradient scrim at 0.28 /
0.42 / 0.55.

If nothing clears the floor it **refuses**, and the run falls back to caption
mode. Illegible text is worse than no text.

**The text is drawn with Pillow, not ffmpeg's `drawtext`.** That filter needs
libfreetype and the Mac's ffmpeg does not have it. Pillow is already a
dependency (`renderer_edu` uses it), so the lane no longer depends on how ffmpeg
was compiled — only on `overlay`, which every build ships.

Proof renders: `selene-dreams-script-v3.0/_Hook Proofs/`.

**This measure-then-decide approach is what the carousel lane is missing and
should be back-ported to `renderer_edu`.**

## The chain

```
00. Drop Here/          you drop a file
   ↓ Drive sync         new files in 01. Video Content -> local pool
   ↓                    (fail-open and LOUD; never re-downloads a deletion)
   ↓ intake             sha256 content hash — renaming does not make it "new"
   ↓ validate           ffprobe: 3s-15min, <90MB, h264/aac, Meta's ratio range
   ↓                    unusable files are marked rejected and never re-probed
   ↓ describe           ffmpeg pulls 6 frames → Claude CLI looks at them
   ↓                    → summary, product, mood, hook, seo_terms  (CACHED)
   ↓ hook               pattern rotation → hook bank → validated
   ↓                    (numbers, questions, banned words all rejected)
   ↓ downscale          >1080px or >12 Mbps -> re-encode to 1080 wide
   ↓                    (always logged; skipped if it would not shrink)
   ↓ overlay            ONLY in overlay mode: measure luminance, pick
   ↓                    treatment, burn in, re-validate; refuse → caption mode
   ↓ caption            reel routing → prompt → validate_caption()
   ↓                    caption mode: caption MUST open with the hook, verified
   ↓                    fails twice = video parked, nothing published
   ↓ host               video pushed to the selene-ig-public repo, raw URL
   ↓ publish            REELS container + trial_params, wait for transcode
   ↓ record             _state/reels.json + caption-log.md
```

## Files

| File | What it is |
|---|---|
| `reel_config.py` | every tunable: cadence, cooldown, eligible styles, paths |
| `video_host.py` | ffprobe validation, lossless `.mov`→`.mp4` remux, GitHub hosting |
| `reel_describe.py` | frame extraction + the vision pass |
| `reel_caption.py` | reel routing, prompt, validation, rotation logging |
| `reel_hook.py` | hook patterns, rotation, mode choice, hook validation |
| `hook_overlay.py` | luminance measurement, treatment choice, ffmpeg burn-in |
| `prompts/reel-hook.md` | the hook prompt (v2026-09-09.v1) |
| `hook-bank-v1.0.md` | the patterns, with provenance (in 03. Content) |
| `reel_runner.py` | intake, state, cadence, the Graph calls, CLI |
| `prompts/reel-caption.md` | the caption prompt (v2026-09-09.v1) |
| `reel_drive.py` | Drive intake: recursive listing, downloads, dedupes, tracks renames |
| `reframe_prep.py` | contact sheets of horizontal footage with candidate 9:16 crops drawn |
| `reel_products.py` | the real catalogue vocab + filename product parser |
| `reel_music.py` | track sync, LRU choice, loudness-normalised mixing |
| `reel_sheet.py` | the sheet mirror: row builder, fail-open append, metrics write, `--rebuild` |
| `post_metrics.py` | carousel results readback, image + edu lanes, 72h/7d, `_state/post-metrics.json` |
| `taste_store.py` | the shared taste layer: collects references/feedback/outcomes from all three lanes into memory repo `taste/` |
| `reel_feedback.py` | reads Q Notes / W Rating + the Taste Notes tab; taste block for the writers; `reel-taste.md` |
| `reel_metrics.py` | reads Instagram results back at 72h and 7d; negotiates the metric set |
| `_tests/run_reel_tests.py` | offline harness for the readback — no network, no credentials |
| `setup_reel_sheet.py` | one-time tab + header + formatting setup |
| `install_reel_agent.command` | LaunchAgent installer |
| `server.py` v3.6 | adds `POST /reel` |

## Commands

```
python3 reel_runner.py --doctor      # check every dependency
python3 reel_runner.py --status      # pool, what is eligible, what is held
python3 reel_runner.py --dry-run     # full chain, stops before publishing
python3 reel_runner.py --run --force # publish one now, ignore the cadence
python3 reel_runner.py --only FILE   # target one file
python3 reel_runner.py --variants    # hooks per video, side by side
python3 reel_runner.py --metrics     # read results back for anything due
python3 reel_runner.py --metrics-now # probe reading now; does NOT consume a window
python3 reel_runner.py --repair-windows  # demote an off-schedule reading to a probe
python3 reel_runner.py --sync        # pull new videos from Drive, then stop
python3 reel_runner.py --index       # give every pooled video a row in the Videos tab
python3 reel_runner.py --feedback    # sync your Notes/Ratings/Taste Notes, print what the writers see
python3 reel_runner.py --taste       # regenerate taste/ in the memory repo and push now
python3 reel_runner.py --post-metrics # read carousel results back now (image + edu)
python3 reel_runner.py --skip-drive  # run without touching Drive
python3 setup_reel_sheet.py          # build the sheet tab (once)
python3 reel_sheet.py --rebuild      # rewrite every sheet row from state
python3 _tests/run_reel_tests.py     # offline tests for the metrics readback
```

---

## Decisions worth remembering

### Reel caption routing (resolves the 2026-09-07 deferral)
Eligible: **One Line · Two Beat · Meet the Product**.
Excluded: The Detail, Three Beats, Care Note — explaining styles assume a reader
who already cares, and a trial reel reaches only strangers. Excluded: Current
Style — sale/promo and The Selene Story only.

With three eligible styles and the no-repeat-within-3 rule, the rotation is a
strict cycle. That is a **feature for your testing goal**: equal sample sizes per
style make the comparison clean.

### No Google Sheet
The carousel lane has a sheet because a human approves rows there. This lane has
no human step. State lives in `_state/reels.json`, which also means a Sheets or
Drive outage cannot stop trial reels.

### It shares the rotation log
Both lanes write `caption-log.md`, so styles rotate across your whole account
rather than each lane collapsing into its own shape. `--doctor` asserts the two
paths still match, because a drift here fails silently.

### Reposting is allowed but bounded
You have not seen duplicate suppression on your own account, so repeats are
permitted: `REPOST_COOLDOWN_DAYS = 45`, `MAX_RUNS_PER_VIDEO = 3`. **Watch for
second runs getting far fewer views than first runs — that is suppression, and
the fix is a longer cooldown, not removing it.**

### Cadence
Max 1/day, minimum 40h apart, 10:00-21:00 HKT, with a 35% random skip per tick so
it does not post on a machine-perfect rhythm.

---

## Known gaps

1. **`ffmpeg` unverified on your Mac.** `--doctor` will tell you.
2. **No down-detector, inherited.** Like the publish lane, this only runs while
   Start Selene AI is up, and nothing alerts you when it is not. Same open gap
   as `selene-publish-runner`; one watchdog would cover both lanes.
3. **Product tags are NOT possible on reels via the API.** Meta's reel-container
   parameter list has no `product_tags` — it's an image-container feature. Your
   carousels tag fine (`publish_runner` v1.2) but that does not transfer. Tag
   manually in the app; the natural moment is after graduating a trial.

4. **Baseline, 2026-09-09 reel, probe at 45h** — the first numbers this lane
   has ever read back:

   | | |
   |---|---|
   | views | 235 |
   | reach | 204 |
   | avg watch | 4.9s |
   | total watch | 16.4 min |
   | likes | 1 |
   | comments / shares / saves | 0 / 0 / 0 |

   Read these as a **starting line, not a result.** One reel, one hook, one
   mode, no comparison. The two numbers worth watching as variants accumulate
   are average watch time (the hook's actual job) and saves (the intent signal
   for bedding — a save is someone thinking about buying). Both are read
   automatically from here on.

4. **Untested links.** Verified here: intake, hashing, validation, variant
   cooldown, the 3-variant cap, cadence, rejection fallthrough, frame
   extraction, style rotation, hook pattern rotation, `has_people` gating, mode
   rotation, hook validation (8 cases), overlay treatment selection on pale /
   dark / mid / brightness-shifting footage, the feathered scrim, and a full
   4-run variant simulation. NOT verified from this machine: the vision pass,
   hook and caption generation, GitHub video upload, and the Meta publish call —
   all need the Mac. Your first `--dry-run` covers the generation stages.

5. **`caption_runner.py:364` rides a deprecation shim.** gspread 6 swapped
   `update()` to `(values, range_name)`; that line still passes the old order.
   It works today and only warns, but it will break when the shim is removed.
   One-line fix (use named arguments) — NOT applied, since that file is behind
   the three hard caption gates and was not in scope. The new sheet code uses
   named arguments and is unaffected.

6. **The hook bank is borrowed evidence.** Every pattern comes from other
   people's accounts. Once enough variants have run, Selene's own results become
   the `OURS` tier and should replace them.

## Cleanup you should do

Four synthetic test clips are sitting in `00. Drop Here/`
(`broken_tooshort.mp4`, `linen_folding.mp4`, `silk_morning.mp4`,
`it_linen_morning.mp4`). They are marked
`retired` in `_state/reels.json` so the lane will never publish them, but they
are noise — drag them to the trash. Copies are in
`selene-dreams-script-v3.0/_to_delete/reel-lane-test-20260909/`.
