# Selene Dreams — Educational Carousel Flow
VERSION 2.0 — 2026-09-09

## Changelog
- **2.0  2026-09-09** — THE FULL FLOW. Writer, caption, final-look email and publishing
  added; every stage runs off the same 15-minute tick. Two post archetypes (taught /
  shown), Real Moments topic type, outro dropped, cover rotation, verified-claims file.
  v3.0 modules are imported read-only; nothing in the image lane changed.
- **1.0  2026-08-28** — Core: plan → arm → render, verified end to end on row 9.

A separate flow beside selene-dreams-script-v3.0. Own sheet, own server (port 5002),
own venv. It imports the image lane's proven pieces (`claude_client`, `image_host`,
the Meta publish primitives, the caption validator and rotation log) from the v3.0
folder and never copies or modifies them. Credentials are likewise referenced, never
copied.

## The tick — what one poke does, in order
launchd `com.selene.edu` POSTs `http://127.0.0.1:5002/tick` every 15 min. Each stage is
fenced; one failing does not stop the rest.

| # | Stage | Module | Reads | Writes |
|---|---|---|---|---|
| 1 | **writer** | `writer_edu.py` | Post Topic rows at `Approved` with empty Slide cells | Slide 1–7 as `Title \| description`, cover choice + general claims in Remark(s) |
| 2 | **plan** | `plan_edu.py` | Approved topics with slide text, no live queue row | Generation Queue row (per-slide source, prompts visible) + Generation Status row, `D=Drafted` |
| 3 | **arm** | `edu_server.py` | `D=Approved` and `E` blank | `E=Ready` |
| 4 | **render** | `render_runner_edu.py` | `E=Ready` | slides in Drive `03. Generated Images/Educational/Row N`, `E=Done` |
| 5 | **caption** | `caption_edu.py` | `E=Done`, `H` not Done | Generated Caption row, `H=Done`, playbook + caption-log entries |
| 6 | **notify** | `notify_edu.py` | `E=Done`, `H=Done`, `K` blank | strip JPG in the row's Drive folder, **email to Marcus**, `K=Review` |
| 7 | **publish** | `publish_edu.py` | `K=Approved` → schedule; `K=Scheduled` + slot passed → fire | `L=date`, `K=Scheduled` → hosted slides, Meta carousel, `K=Posted`, `M=date`, permalink in queue col R and Post Topic `Post url` |

## Marcus's gates — two per post
1. **Words + plan** — `D=Approved` in Generation Status. The writer has already drafted
   every slide; edit the cells in Post Topic if anything is off, then flip D.
2. **Final look** — the emailed strip. Set `K=Approved` from your phone. Anything else in
   K holds the post.

Topic approval (`Status=Approved` in Post Topic) is pool maintenance, not per-post.

## Post-Status vocabulary (col K)
blank → `Review` (strip emailed) → `Approved` (you) → `Scheduled` (runner, date in L) →
`Posted` (date in M). `Hold` = a failure, reason in col N. To cancel a scheduled post,
change K to anything other than Scheduled before the slot.

## Schedule
Educational takes **Thursday 21:00 America/New_York** (`POST_WEEKDAY` in config_edu).
The image lane keeps Tue/Sat. Chosen on benchmark grounds, not on Selene's own data —
change the one config line once outcomes exist. One educational post per Thursday.

## The two archetypes
- **Taught** — cover + a bubble card on every interior. All nine original topic types.
- **Shown** — cover + bare photographs, text on the thumbnail only. Topic type
  **Real Moments**. Only the cover line goes through the words gate.

No outro on either. The caption is the only shop pointer (`selenedreams.com` once in the
body); no product tags on this lane.

## Copy rules the runners enforce
- Character caps come from the real fonts at the real sizes (`_Template Kit/TEMPLATE-SPEC.md`).
  The writer validates with the renderer's own measurement; overflow gets two rewrite
  rounds, then the row is flagged and left blank.
- Product facts may only come from `prompts/claims_edu.md`. Any general-knowledge line the
  model uses is surfaced in the row remark as **GENERAL CLAIMS (verify)**.
- No dash punctuation, no exclamation marks, talking-to-you register on interior slides.

## Mail (final look)
Gmail SMTP with an app password, read from the v3.0 `.env`:
```
SELENE_MAIL_FROM=you@gmail.com
SELENE_MAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```
Not configured → the strip is still saved to Drive and K still becomes Review.

## Files
config_edu.py v1.1 · templates_edu.py v1.8 · renderer_edu.py v1.3 · sheets_edu.py ·
library_edu.py v1.2 · plan_edu.py v1.5 · render_runner_edu.py v1.2 · writer_edu.py v1.0 ·
caption_edu.py v1.0 · notify_edu.py v1.0 · publish_edu.py v1.0 · edu_server.py v2.0 ·
log_edu.py · setup_edu_v2.py (one-off migration) · prompts/ (writer_edu, caption_edu,
caption_review_edu, claims_edu) · _Template Kit/ · fonts/ · _logs/ · _state/

## CLI
```
.venv/bin/python writer_edu.py --dry-run --topic 3     # draft to stdout, write nothing
.venv/bin/python caption_edu.py --number 10            # caption one row
.venv/bin/python notify_edu.py                         # email pending strips
.venv/bin/python publish_edu.py --next-slot            # print the next free Thursday
.venv/bin/python publish_edu.py --dry-run              # schedule + pretend to fire
.venv/bin/python setup_edu_v2.py [--apply]             # the v2 sheet migration
```

## Still not built
- Legibility QA (pale photos swallow the type — mockups A5/B6). Marcus's eye is the check.
- Cover-history seeding from the v3.0 lane's posted covers.
- Outcomes (saves/shares) collection for own posts — Meta insights scope unverified.
- Server down-detector (same gap as the image lane).
