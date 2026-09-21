# The Taste Layer — one brain for three flows

**VERSION 1.3 — 2026-09-16**

## Changelog
- **1.3 — 2026-09-16** THE POSTED CONTENT SHEET. Marcus asked for one sheet for
  every published post so he can comment on each. `posted_sheet.py`: tab
  **Posts** (A-M machine: lane, posted, what, choices, permalink, metrics at
  72h/7d; **N Rating / O Notes** his), rows keyed by permalink, every lane incl.
  **manual** (hand-posted, found by one walk of the account, last 50; metrics
  read for those too — post_metrics 1.1). Tab **Taste Notes** moves here. Read
  back by reel_feedback 1.1 (reel ratings still weight the rotation) and
  taste_store 1.2 (all lanes; taste notes of EVERY scope — the images-scoped
  ones never reached the brief before). Mirrored every reel tick (1.17).
  The old per-lane columns still feed; this is the one place to write.
- **1.2 — 2026-09-16** LANE ROUTING after the first live distill (8 visual
  principles, all from reference notes, went to every writer incl. copy). A
  reference-only principle is now `[visual]` and reaches only picture stages;
  `brief_block(stage)` filters per writer. Re-run `--distill --force` once.
- **1.1 — 2026-09-16** STEP 3: THE BRIEF. `taste_brief.py` distils the three raw
  files into `taste/brief.md` (≤10 principles, each with a verbatim quote and a
  source; the code DROPS anything uncited — the guard against generic mush),
  versioned `date.vN` with a changelog. Runs weekly before Monday screening and
  is stamp-checked on the reel tick; skipped when nothing changed since the
  last distill. `{taste_brief}` is now in ALL EIGHT writer prompts: image-prompts
  v5, screening v5, caption v5, reel-hook v5, reel-caption v5, writer_edu v6,
  picker_edu v3, caption_edu v5. Writers read a local cache
  (`_state/taste-brief.md`) refreshed on every distill and every taste sync;
  missing cache = one-line placeholder, brand guide governs.
- **1.0 — 2026-09-16** First build: collectors + files (steps 1 and 2). The
  distill step (`taste/brief.md`) and injecting it into every writer are the
  next build.

## Why
Marcus, 2026-09-16: keep the image, educational and reel flows SEPARATE — they
differ — but make what they learn about his taste communicable, so every
writer understands what content he wants and the data accumulates in one
place. Before this: the screener learned from picks, the reel lane from its
sheet, the educational lane from nothing; nothing crossed lanes.

## Where
`selene-ig-memory` (GitHub), folder `taste/`. Every lane already clones and
pushes it; Apps Script and the cloud research agent already read it.

## Files (machine-written, regenerated whole every sync — never hand-edited)
| file | what | source |
|---|---|---|
| `taste/references.md` | every reference image + vision note, by lane | Drive `02. Reference Images` via `reference_drive.py` |
| `taste/feedback.md` | every note/rating, any lane, in Marcus's words | Trial Reel sheet Q/W · Taste Notes tab · image-lane Generation Status col N · edu Generation Status col O |
| `taste/outcomes.md` | what the audience did, at fixed ages (72h, 7d) | `reel_metrics` (reels) · `post_metrics` (carousels, image + edu) |
| `taste/*.json` | same data for code | |
| `taste/brief.md` | the compiled "what Marcus wants" block for every writer | `taste_brief.py` — weekly distill, every line cited, versioned with changelog |

## Where you write — ONE place (since 1.3)
**Selene Dreams - Posted Content** (Drive → 10. AI Generation)
https://docs.google.com/spreadsheets/d/19evO6rmh-O9jMmQVUqu0ctV8Z9RRXArFt2xyP6i0bfE/edit
- Tab **Posts**: every published post, every lane (reels · images · educational ·
  manual). **N Rating (1-5)** and **O Notes** are yours. A reel's rating also
  weights hook-pattern rotation.
- Tab **Taste Notes**: general directions (Applies to: all / reels / images /
  educational). Seen is stamped when read.
- Reference images: Drive `02. Reference Images / 01. Style` or `02. Educational`.
- Still honoured, no longer needed: Trial Reel Q/W, Generation Status col N (images) / col O (edu).
- Setup once: `python3 posted_sheet.py --setup` · fill: `python3 reel_runner.py --posted`
  · re-walk the account for older posts: `python3 posted_sheet.py --rewalk`

## How it runs
- `post_metrics.pass_over()` and `taste_store.maybe_sync()` run on the reel
  lane's 15-minute tick (`reel_runner` 1.15), fail-open, bounded. taste/ is
  pushed at most every 6 h. Force: `python3 reel_runner.py --taste`,
  `python3 reel_runner.py --post-metrics`. Preview without pushing:
  `python3 taste_store.py --local` → `_state/taste-preview/taste/`.
- Carousel media ids come free from the system remark publish_runner writes
  ("published, media <id>"); posts published by hand are resolved by walking
  the account's media once and cached.

## The brief (step 3)
- `python3 taste_brief.py --distill` (add `--force` to redo with unchanged input)
- `python3 reel_runner.py --brief` — exactly what every writer receives now
- Correct a wrong line by writing in the Taste Notes tab; the next distill has it.
- Guard: a principle without a verbatim quote from feedback.md / references.md
  is deleted before the brief is written. Outcomes can support a principle but
  never be its only source.

## The rule
Taste changes HOW things are written. It never decides WHETHER something
publishes. No approval gate has been added anywhere by this layer.

## Known gaps
1. First real distill not yet run — until then writers get the placeholder.
2. Carousel outcomes carry product/type but not caption style or prompt; join
   to caption-log.md / prompt-playbook when the distill step needs it.
3. `outcomes_runner.py` (Apify-based) still exists and still writes
   `post-outcomes.csv`; `post_metrics` supersedes it for reach/saves/shares.
   Retire it once `post_metrics` has read a real window.
4. Not verified live: every Sheets/Graph call in `post_metrics` and
   `taste_store` was stub-tested only (Cowork cannot reach Google/Meta).
