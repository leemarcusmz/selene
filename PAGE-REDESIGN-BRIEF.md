# Selene Dreams — AI Generation Flow: page redesign brief
Version 1.0 · 2026-09-09 · author: Claude (for Marcus)
Purpose: input document for Claude Design. Describes the pipeline in brief, then the two
web pages (picker + review) in enough detail to redesign them.

## Changelog
- 1.0 (2026-09-09) — first issue. Sourced from picker.gs v3.5 build 2026-09-08.b and
  review.gs v1.7 build 2026-08-26.b.

---

## 1. The AI generation flow (brief)

Weekly Instagram content pipeline. Google Sheet = database, Apps Script = web UI + triggers,
a Mac (Flask on :5001, exposed via a static ngrok domain) = all heavy work, GitHub repo
`selene-ig-memory` = state + image archive.

1. **Research (Mon)** — agents scrape/inspect competitor IG posts, write `candidates` to the repo.
2. **Screening** — vision agent scores each candidate for brand fit (x/12), sorts, writes
   `shortlists/shortlist-YYYY-MM-DD.json`. Thin weeks are topped up with 8+ scorers from earlier weeks.
3. **Picking → PAGE 1 (picker)** — teammates open the link, choose individual *images*.
   First valid submission wins the week. Winning pick POSTs `/select` to the Mac.
4. **Prompt writing** — `prompt_runner.py` downloads the chosen reference slides, writes up to
   5 image prompts per post, appends rows to the Generation Queue sheet.
5. **Image generation** — Generation Status col D flips Ready → Apps Script webhook → `generate.py`
   → Nano Banana Pro via Replicate ($0.24/image) → Drive folder per row → D=Done.
6. **Captioning** — event-driven off generation; `caption_runner.py` invokes Claude CLI headlessly,
   writes to the Generated Caption tab → col G=Done.
7. **Approval → PAGE 2 (review)** — the single human gate. Approve/drop/reroll/reject.
   Approve writes J=Scheduled + K=date + P=slide order.
8. **Publishing** — `publish_runner.py` posts to Instagram automatically on the scheduled date
   (Tue/Thu/Sat, 21:00 America/New_York), strips C2PA/XMP metadata, writes the permalink into col O,
   J=Done. Failures park at J=Hold and surface on the review page + by email.
9. **Outcomes** — `outcomes_runner.py` scrapes live metrics off col O into `post-outcomes.csv`.

Both pages are served by ONE Apps Script web app (`/exec`). Apps Script permits exactly one
`doGet` per project, so `picker.gs` routes: default → picker, `?view=review` → review,
`?view=status` → dashboard.

---

## 2. PAGE 1 — "Selene Picks" (picker.gs v3.5)

### Job
Let teammates (and Marcus, under the same rules) pick which competitor images become this week's
prompts. Race condition by design: **first valid submission wins the week**, everyone after sees
a locked "this week is picked" card.

### Data
Shortlist JSON from GitHub. Each entry: `n`, `origN`, `archiveWeek`, `source` (@handle or #tag),
`images[]` (live Instagram CDN URLs), `caption`, `brandRationale`, `postUrl`, `product`
(fabric · productType · variant), `brandScore` (x/12), `likes`, `comments`, `type`, `carriedFrom`.
Rows are sorted by brandScore descending.

### Current layout (top to bottom)
- **Header** — `Selene Picks — week of YYYY-MM-DD`, 22px, 2px dark bottom rule. Below it a 13.5px
  grey "lede" paragraph, ~820px wide, explaining the rules in prose (rank order, click images not
  posts, first 15 become prompts, overflow auto-saves, max 5 per post, first submission wins).
  **This paragraph is doing far too much work — it is the entire rulebook as a wall of text.**
- **Optional section: "Saved from earlier weeks"** — small caps 11px section label. Shelf rows,
  rendered with dashed border + cream background, no "save" button (already saved).
- **Section: "This week's shortlist"** — the ranked rows.
- **Post row card** (white, 2px border, 16px radius, 22-24px padding, 22px gap; max-width 1240px):
  - Header line, flex/baseline: rank pill ("Best fit" inverted dark, then "#2", "#3"…),
    title ("Selene Pick 4"), source handle (blue) or hashtag (orange), optional gold
    "held over from <week>" note, and right-aligned live counter "n of 5 chosen".
  - Stat pill row: image count, likes, comments, media type, "brand fit 9/12" (blue pill),
    product string (green pill).
  - Original caption block: cream, 3px sage left rule, pre-wrapped, uppercase micro-label.
  - Rationale line (12px grey) + "open original post ↗" link.
  - **Image strip**: horizontal flex-wrap of fixed 172px-wide tiles, 215px tall cover-cropped,
    3px border, 12px radius, 14px gap. Per tile: slide number badge (top-left), selection order
    badge (top-right, dark = counted, gold "next wk" = overflow), full-bleed checkmark overlay
    when selected, and a hover action row bottom-right with `save` and a zoom (⌖) button.
    States: `.sel` dark border, `.saved` gold, `.queued` gold dashed + 88% opacity,
    `.expired` "recovering…", `.gone` "image expired" at 45% opacity.
- **Fixed bottom bar** (full width, white, 2px top rule, z-20): live count
  "7 of 15 images across 3 posts · 4 saved for next week", a name text input, a ghost gold
  "Save marked" button, a solid dark "Submit picks" button, plus a full-width error line (red)
  and success line (green) that wrap underneath.
- **Lightbox** — click ⌖ → near-black full-screen overlay, image max 92vw/88vh, Close button
  top-right, Esc closes.
- **Footer** — 10.5px grey "picker build 2026-09-08.b".

### Interaction model (must survive any redesign)
- Selection is **per image, never per post**. There is deliberately no "select this post" control.
- **Click order is the model.** `ORDER[]` is an array; first 15 entries become this week's prompts,
  everything after is auto-saved to next week's shelf. No one ever has to choose what to drop.
- Hard error (blocks submit): more than 5 images from one post — a post becomes one queue row and a
  row has exactly 5 prompt columns. Error text names the offending post.
- Submit sequence: `submitPicks()` first (wins or loses the lock), *then* `saveToShelf()` for the
  overflow. Losing the race must not shelve images.
- Broken CDN images self-heal: `onerror` → `archivedImage(week, origN, i)` pulls the archived
  640px thumbnail from the repo. Carried rows are already data-URLs.
- Everything is `google.script.run` async; the page never navigates.

### Palette / type in use
`--bg #F5F3EF · --ink #273F22 (deep green) · --soft #6f7768 · --line #ded9cc · --ecru #E8E4D8 ·
--sage #7C896F · --wedge #335875 (blue) · --apricot #b8552f · --gold #8a6d3b`.
System font stack. Desktop-first, max 1240px; one mobile breakpoint at 620px turns tiles into
2-up 50% and drops padding.

### Known weaknesses to design against
1. The rules live in a paragraph nobody reads; the cap, the per-post limit and the overflow
   behaviour are only discoverable by hitting them.
2. Long weeks = very long scroll. No sticky rank/nav, no way to compare across posts, no filter
   (e.g. by product type or score threshold).
3. The bottom bar mixes three unrelated things: status counter, identity (name), and two
   different commit actions. "Save marked" vs. auto-overflow-save is genuinely confusing —
   two paths to the same shelf.
4. Name entry is an afterthought at the bottom, but it is required and the week is a race.
5. Fixed 172px tiles waste a wide screen and crush a phone; the strip does not communicate
   "this is a carousel from one post" strongly.
6. No indication of what the picked images will become (a prompt, then an image) — the mental
   link to the review page is missing.

---

## 3. PAGE 2 — "Selene Review" (review.gs v1.7, `?view=review`)

### Job
The single human gate. Shows every row where Generation Status D=Done AND G=Done AND J is blank /
"Not Started", drawn as a mock Instagram post. Marcus approves, drops slides, reorders, rerolls,
or rejects. Approve → J=Scheduled, K=date, P=approved slides in displayed order; the publish runner
posts it automatically on that date.

### Data per card
Row number, product title (fabric · type · variant), Drive file IDs for each slide, the generated
caption, an optional caption-QA remark. Thumbnails are **not** in the initial HTML — the page
returns immediately with placeholders and pulls 900px Drive thumbnails via `reviewThumb()`,
two in flight at a time (v1.6 fix: prefetching them all blew the request timeout).

### Current layout
- **Centred column, max-width 540px** — deliberately phone-shaped; this page is used on a phone.
- **Header** — "Selene Review" + "3 posts ready for you" (or "Nothing waiting.").
- **Empty state** — bordered card explaining posts appear once images + caption are both done,
  and that an ERROR row will never reach this screen.
- **Feed of cards** (white, 1px border, 14px radius, 22px gap). Each card:
  - **Card head**: circular gradient avatar, `selenedreams_official`, sub-line
    "Silk · Pillowcase · Ivory · row 14", right-aligned "3 slides" counter.
  - **Rail**: horizontal scroll-snap carousel, each slide 100% width, 1:1 aspect, cover-cropped.
    Badge top-right shows slide number, and " · cover" on the first kept slide.
    Dropped slides go greyscale under a dark "DROPPED" overlay.
  - **Slide bar** (under each slide): ◀ ▶ move buttons (reorder within the carousel),
    `Drop` (toggles to "Undo drop", free), `Reroll $0.24` (confirm dialog, max 2 per slide;
    the whole row goes back to generating and the card settles with "reload once it finishes").
  - **Cover warning strip** (apricot, only when slide 1 is dropped/moved):
    "Slide 3 is now your cover / grid thumbnail."
  - **Caption block**: uppercase label + hint "edit inline, it saves with Approve", a 6-row
    textarea, and optional "Caption QA: …" remark line.
  - **Actions row**: a native `<input type=date>` labelled "Post on" (defaults to today), a
    primary `Approve` button that self-labels — "Approve 3 slides", "Approve 1 slide (single image)",
    or disabled "Nothing left to post" — and a ghost `Reject`.
  - **Reject box** (revealed): free-text "Why? a few words — this is what teaches the rubric"
    + red "Confirm reject" + cancel. Empty reason is refused.
  - **Posting kit** (revealed after approve, pale green): "Copy caption", "Download slides"
    (opens each kept slide's Drive link in a new tab), and a URL field + Save that writes column O.
    Note: with autopublish live this kit is now mostly the manual fallback.
  - **Settled state**: card drops to 55% opacity, rail/caption/actions hide, a single line of
    outcome text remains ("Rejected — shelved, and the reason is on the row.").
- **Scheduled section** (below the feed, no images so it stays cheap): one compact row per
  J=Scheduled / J=Hold post — title, "row 14 · slides 1,3,2 · posts 2026-09-12 (9 PM New York)",
  `Cancel` (returns it to the feed), and for failed rows an apricot border plus
  "PUBLISH FAILED — <last system remark>" and a `Retry`.
- **Toast** — dark pill, bottom-centre, slides up, 3.2s, red variant for errors.
- **Footer** — "review build 2026-08-26.b · drop is free · reroll is $0.24 · nothing here posts
  to Instagram by itself". (That last clause is now **false** — publishing is automated.)

### Interaction rules that must survive
- DOM order of slides IS the post order. Approve saves col P in displayed order ("3,1,2") and the
  publish runner posts P verbatim. First kept slide = cover = grid thumbnail.
- 1 kept slide → single-image post. 2–10 → carousel. 0 → approve disabled.
- All writes go through a LockService lock (two phones on the same link would interleave).
- A global `busy` lock disables every button during any server call.
- Reroll costs money and is capped at 2 per slide; drop is free and is the intended primary lever.

### Palette / type in use
Same base as the picker: `--bg #F5F3EF · --ink #273F22 · --soft #6f7768 · --line #ded9cc`,
plus `--ok #3d6b34 · --warn #FF6F55 · --danger #c2492f · --new #335875 · --mut #f1efe8`.

### Known weaknesses to design against
1. The Instagram mimicry is skin-deep — a fake avatar and handle, but the rail is one slide per
   viewport with no dots/progress, so on desktop you cannot see the carousel as a set. Comparing
   slides (the actual job when deciding what to drop) is impossible without scrolling back and forth.
2. Reorder via ◀ ▶ on a 4-slide carousel is slow and easy to lose track of; there is no
   thumbnail strip showing final order.
3. Every slide carries its own 4-button bar → 16 buttons on a 4-slide post, all identical weight.
4. Approve/Reject sit at the very bottom of a long card; the date picker defaults to *today*
   even though the real cadence is Tue/Thu/Sat 21:00 NY — the page knows the cadence and does not
   offer it.
5. The posting kit is dead weight in the automated flow but still occupies the post-approve state.
6. The footer text is stale and contradicts the actual behaviour.
7. 540px cap means a desktop screen is ~75% empty; this page is used on both.

---

## 4. Hard constraints for any redesign

- **Google Apps Script HtmlService.** Page is HTML built as a concatenated string inside a `.gs`
  file and served in a sandboxed iframe. No build step, no framework, no bundler.
- **One `doGet` per project.** Every page must be routed from `picker.gs`'s `doGet`.
- Server calls are `google.script.run.withSuccessHandler(...).fnName(args)` — async, no fetch to
  the sheet, no REST. Return values must be JSON-serialisable.
- Images: picker uses live IG CDN URLs (they die within days) plus repo data-URLs; review uses
  Drive thumbnails fetched lazily as data-URLs, ~2 concurrent, 6h cache, 95KB cache cap.
  **Never prefetch all images server-side — that is what hung the review page.**
- Deployment: editing code changes nothing until Deploy → Manage deployments → *edit the existing
  deployment* → New version. A new deployment = new URL = every emailed link is orphaned.
  The build stamp in the footer exists to expose a stale deployment — keep it.
- Access is "Anyone with the link", no Google login; identity on the picker is a typed name.
- Both pages must work on a phone. Review is phone-first; picker is currently desktop-first.
