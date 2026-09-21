# Selene Dreams — round-2 design prompts (picker + review)
Version 1.2 · 2026-09-09 · follows PAGE-REDESIGN-AUDIT.md v1.0 and Marcus's decisions of 2026-09-09.
Desktop only this round; mobile after.

## Changelog
- 1.2 (2026-09-09) — split-post requirement REMOVED (deferred, not a requirement for now). Validation item 9 now reads per-post cap only.
- 1.1 (2026-09-09) — split flow settled: group chip on tile (A/B/C cycle), replaces the header toggle + tabs. Decision: 1 picked image = single-image post; no "expand to carousel" yet.
- 1.0 (2026-09-09) — first issue.

## Decisions recorded 2026-09-09
- Fabric filter chips: dynamic from the week's data.
- One shortlisted post may be SPLIT into several Selene posts (groups A/B/C). PIPELINE CHANGE:
  picker.gs sends the same n once per group; prompt_runner.py must create one queue row per group.
- Reroll and Reject live in the per-slide "···" / action bar; requirements below.
- Manual post-URL entry: NOT needed (col O is auto-filled by publish_runner).
- Calendar: no per-day status boxes; show a COUNT per day + type dots; day panel on click;
  multiple posts per day allowed; non-cadence days selectable.
- Post types on the calendar: AI carousel, Educational, Reel, Trial reel (edu/reel/trial live in
  OTHER sheets — review.gs will need SpreadsheetApp.openById to aggregate).
- Hold/failed handling: runner auto-retries once after 15 min; page shows a NEEDS ATTENTION group
  with Retry now / Reschedule / Cancel; calendar day count turns red; email stays.

## PICKER — prompt
Keep the current "Selene Dreams Research Picks" design as the base. Desktop only for now. Add the following. Fabric filter chips are generated from the week's data, never fixed.

1. OVERFLOW STATE (16+ images chosen)
- Slot meter is full and reads "15/15 · +3 next week".
- Count line reads "15 images across 6 posts · 3 saved for next week".
- Tiles chosen beyond slot 15 get a gold dashed border and a gold badge "next wk" in place of the order number; their bottom label reads "→ saved for next week" instead of "→ prompt NN".
- Nothing is blocked; the user keeps clicking.

2. ZOOM / LIGHTBOX
- Every tile has a small zoom icon bottom-right (visible on hover). Clicking it opens a full-screen lightbox: near-black backdrop, image at max 92vw / 88vh, Close button top-right, ← → to move between slides of the same post, Esc closes. Clicking the tile itself still selects it — zoom must not toggle selection.

3. EXPIRED-IMAGE STATES (Instagram links die within days)
- "recovering…" — tile shows a muted placeholder with a small spinner and the text "recovering from archive".
- "image expired" — tile at 45% opacity, red text "image expired", not selectable.
- Show one post row with one of each.

4. (removed — split-post feature deferred 2026-09-09)

5. SHELF ROWS — "Saved from earlier weeks"
- A section above "This week's shortlist" with the label SAVED FROM EARLIER WEEKS. Rows here use a dashed border and a cream background, no rank badge, a gold tag "saved 2026-08-31 · by Dana R.", and no "save" action.
- Separately, a normal shortlist row can carry a gold tag "held over from 2026-08-24" (a high scorer carried into a thin week). Show one of each — they are different things.

6. WEEK-LOCKED VIEW (replaces the whole page once someone has submitted)
- Centred card: "This week is picked". "Dana R. chose 12 images across 5 posts · 2026-09-08 14:12". Below: the picked tiles as a compact read-only grid with post handles. Footer line "Next shortlist lands Monday."

7. POST-SUBMIT VIEW (what the winner sees)
- Centred card: "You got it". Line 1: "12 images across 5 posts are being written into the queue." Line 2 (only if overflow): "3 image sets saved for next week." Same compact read-only grid.

8. LOST-THE-RACE ERROR
- Inline under the Submit button, red: "Someone submitted before you — this week is locked. Reloading…" Submit disabled.

9. VALIDATION
- Submit disabled with no name; hint under the name field "Type your name to submit".
- If a post reaches 5 chosen images: the remaining tiles in that post become non-clickable with a tooltip "5 is the max for one post". Never a page-level error.

10. FOOTER
- 10.5px muted, centred: "picker build 2026-09-09.a". Always present.

## REVIEW — prompt
Keep the current "Selene Dreams Post Review 2a" desktop design as the base. Add the following.

1. "···" MENU ON EACH SLIDE — define its contents
- Reroll ($0.24) — shows "attempt 1 of 2"; disabled with "reroll limit reached" after 2.
- Move to front (make cover)
- Open in Drive
- Drop / Undo drop stays as the primary button outside the menu.

2. REROLL FLOW
- Confirm dialog: "Reroll slide 3? $0.24, about a minute. This post leaves the review queue until it finishes."
- After confirm, the post moves in the sidebar into a group "REGENERATING" with a spinner and "slide 3 · attempt 1 of 2". Main pane shows an empty-ish state for that post: "Rerolling slide 3 — back in the queue in about a minute."

3. REJECT FLOW
- Clicking Reject opens an inline box under the action bar: text field "Why? A few words — this is what trains the rubric", required; buttons "Confirm reject" (red) and Cancel. Empty reason is refused with an inline hint.
- After confirm: post leaves the sidebar, toast "Rejected — reason saved to the row".

4. COVER
- First thumb in the FINAL ORDER strip carries a "cover" label. When the original slide 1 is dropped or moved, show an apricot strip under the FINAL ORDER row: "Slide 3 is now your cover / grid thumbnail."

5. CAPTION QA NOTE
- Under the caption box, a muted collapsible line: "Caption QA · 2 notes ▾". Expanded, it lists the QA notes (e.g. "Avoid the word 'luxury' — banned list", "Hashtag count 3, target 3–5"). Editing the caption does not clear them.

6. POST-APPROVE STATE
- Toast bottom-centre: "Approved — 4 slides, carousel, posts Sat 09-12 21:00 NY". Post leaves "Waiting on you"; sidebar auto-selects the next pending post; the calendar day count increments. If nothing is left, show the empty state.

7. EMPTY STATE (main pane, no pending posts)
- Centred: "Nothing waiting on you." Sub: "Posts appear here once images and caption have both finished. A row stuck on ERROR never reaches this screen — check the Generation Status tab." Sidebar and calendar remain.

8. LOADING / FAILED THUMBNAILS
- Slides load after the page paints: show a muted placeholder "slide 2 · loading…". Failed: "slide did not load" + one line of grey error text + a "retry" link.

9. CALENDAR — replace the per-day status boxes
- Each day shows only a count of posts scheduled/published that day (e.g. "2"), plus small type dots underneath. No dashed "awaiting approval" boxes; unapproved posts have no date.
- Post types, each with a colour and a 2-letter tag: AI carousel (AI), Educational (ED), Reel (RE), Trial reel (TR). Add a legend.
- Cadence days (Tue/Thu/Sat) are bold; every day is selectable, including non-cadence days.
- Multiple posts on one day are allowed. When picking a date that already has a post, show a soft note under the date button: "2 posts already on Sat 09-12" — informational, not blocking.
- Day panel: clicking a day opens a panel (right of the calendar or as a popover) listing that day's posts: type tag, title, row, status (scheduled / published / failed), time, and actions — scheduled: Cancel; published: "open on Instagram"; failed: Retry now · Reschedule · Cancel.

10. FAILED / HOLD POSTS
- Sidebar gets a red group NEEDS ATTENTION above WAITING ON YOU. Each item: title, row, "publish failed · Sat 09-12".
- Selecting one opens the normal post pane in a failed state: red banner at the top with a plain-language reason (e.g. "Instagram rejected the image — over 8 MB") and the raw last system remark in small grey text. Action bar becomes: Retry now · Reschedule (opens date picker) · Cancel (back to review). Slides and caption are read-only here.
- Show one failed post in the sidebar and one open in the main pane.

11. FOOTER
- "review build 2026-09-09.a · drop is free · reroll is $0.24 · approved posts publish themselves"
