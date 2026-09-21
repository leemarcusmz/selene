# Selene Dreams — mobile design prompts (picker + review)
Version 1.0 · 2026-09-09 · companion to PAGE-REDESIGN-ROUND2-PROMPT.md v1.2 (desktop).

## Changelog
- 1.0 (2026-09-09) — first issue.

## Shared constraints (both pages)
- Target 390×844 (iPhone 14/15 class); must also hold at 360 wide. Portrait only.
- Same palette, type and tokens as the desktop designs. Same build-stamp footer.
- Min tap target 44×44. No hover states — every hover affordance on desktop needs a visible
  or tap-revealed equivalent.
- No HTML5 drag-and-drop (dead on iOS Safari). Reorder uses ◀ ▶ buttons or long-press-and-move.
- Bottom sheets for menus and pickers, not popovers.
- All actions that write to the sheet keep the same names and outcomes as desktop.

## PICKER — mobile prompt
Mobile version of "Selene Dreams Research Picks". Teammates use this on their phone, one-handed, often on Instagram-quality images. Show these screens: default with a few picks made, one post card expanded, the lightbox, the overflow state, the week-locked view.

1. STICKY HEADER (compact, ~56px)
- Line 1: "Research Picks · wk 09-07". Right side: slot meter as a thin bar with "8/15" beside it.
- Line 2 collapses on scroll: "12 posts · ranked by brand fit".
- A small "?" opens a bottom sheet with the four rules (the desktop chips) — rules are not shown inline on mobile.

2. NAME + FILTERS
- Under the header, one row: "Picking as" text field, full width. If empty, it has a soft red outline and Submit stays disabled.
- Filter chips in a horizontally scrolling row: all · fit ≥ 9 · <fabrics from data> · carousels only. Active chip inverted.

3. POST CARD (full-bleed, stacked)
- Header row: rank pill ("Best fit" / "#2") · handle · brand-fit score pill "11/12". Right: "3 of 5" dots.
- Second row of pills: image count · likes · comments · product string. Wraps to two lines if needed.
- "Their caption" and "Why it scored" are collapsed by default behind a single line "caption · why it scored ▾" and expand together.
- IMAGE GRID: 3-across square tiles, 4px gap, full card width (≈ 118px each at 390).
- Tile overlays: slide number top-left; order badge top-right ("01"…"15" dark, or gold "next wk"); a small "→ prompt 01" pill bottom-left on chosen tiles; a zoom glyph bottom-right, always visible, 44px hit area.
- Tap tile = select/deselect. Tap zoom glyph = lightbox, must not toggle selection.
- When a post reaches 5 chosen, remaining tiles dim and show a lock glyph; tapping shows a toast "5 is the max for one post".

4. LIGHTBOX
- Full-screen, black, swipe left/right between slides of the same post, pinch to zoom, X top-right, slide counter "3 / 6" bottom-centre. A "Select" / "Selected ✓" button at the bottom.

5. STICKY BOTTOM BAR (safe-area aware)
- Left: "8 of 15 · 3 posts" and, if overflow, a second line "3 saved for next week" in gold.
- Right: "Submit picks →" primary button. Disabled until name entered and ≥1 chosen.
- "Clear all" as a small text link in the bar, left of Submit — confirm toast with Undo (5s).

6. STATES
- Overflow (16+): meter full, gold "next wk" badges, bottom-bar second line.
- Expired image: "recovering…" tile with spinner; "image expired" tile dimmed with red label, not tappable.
- Shelf section "Saved from earlier weeks" above the shortlist, dashed cards, gold "saved 08-31 · Dana R." tag. Held-over rows carry a gold "held over from 08-24" tag.
- Week-locked view: full-screen card "This week is picked", who / how many / when, compact 3-across grid of the picked tiles, "Next shortlist lands Monday."
- Post-submit view: "You got it", counts, overflow line if any, same grid.
- Lost the race: inline red line above the bottom bar, then reload.

7. FOOTER
- "picker build 2026-09-09.a", muted, under the last card.

## REVIEW — mobile prompt
Mobile version of "Selene Dreams Post Review 2a". The three-column desktop layout becomes two top-level tabs plus a detail screen. Show: Queue tab, Post detail, Post detail with ··· sheet open, date bottom sheet, Reject inline, Calendar tab, Day sheet, Needs-attention post detail, empty state.

1. TOP BAR + TABS
- Title "Post Review". Sub-line "publishing is automatic · Tue / Thu / Sat · 21:00 NY" small mono.
- Segmented control: "Queue (3)" · "Calendar". Persisted across reloads.

2. QUEUE TAB
- Group "NEEDS ATTENTION" (red, only if any): title · "row 14 · publish failed · Sat 09-12".
- Group "WAITING ON YOU": 44px square thumbnail, title, "row 14 · 5 slides".
- Group "REGENERATING" (only if any): spinner, "slide 3 · attempt 1 of 2".
- Tap a row → Post detail (push, with back).
- Empty: "Nothing waiting on you." + desktop sub-line.

3. POST DETAIL
- Header: back, title, "row 14 · 5 generated · 1 dropped · carousel of 4".
- FINAL ORDER strip: horizontal 64px thumbs, numbered, first labelled "cover". Tap jumps the carousel. Reorder via long-press-and-move, with ◀ ▶ in the ··· sheet as fallback.
- Cover warning strip (apricot) when slide 1 is no longer first.
- MAIN CAROUSEL: full-width square, swipe, scroll-snap, dots + "slide 3 · 4" counter. Dropped slides greyscale with "DROPPED" overlay, still in the carousel.
- Under the carousel, for the CURRENT slide: [Drop / Undo drop] full-width secondary + [···] 44px.
- ··· bottom sheet: Reroll ($0.24 · attempt 1 of 2), Move earlier, Move later, Make cover, Open in Drive, Cancel.
- CAPTION: label, auto-growing textarea (min 5 lines), collapsible "Caption QA · 2 notes ▾".
- STICKY BOTTOM ACTION BAR: [📅 Sat 09-12] · [Approve 4 slides] primary flex-grow · [Reject] text-danger. 0 kept → "Nothing left to post", disabled.

4. DATE BOTTOM SHEET
- Month grid, Tue/Thu/Sat bold, every day selectable, per-day count + type dots. Selecting a day with posts: soft note "2 posts already on Sat 09-12 — that's fine". "Use Sat 09-12" primary, Cancel.

5. REJECT (inline panel above the action bar)
- Required reason field, "Confirm reject" red, Cancel. Empty reason refused inline.

6. REROLL FLOW
- Confirm sheet → toast → pop to Queue; post under REGENERATING.

7. POST-APPROVE
- Toast "Approved — 4 slides, carousel, Sat 09-12 21:00 NY". Pop to Queue; next row highlighted briefly.

8. CALENDAR TAB
- Month header ‹ › + "4 out · 2 queued". Each day: count + up to four type dots (AI · ED · RE · TR). Cadence columns bold. Failed → red count. Legend under grid.
- Tap day → DAY SHEET: list with type tag, title, row, status, time; actions: scheduled → Cancel; published → Open on Instagram; failed → Retry now · Reschedule · Cancel.

9. NEEDS-ATTENTION POST DETAIL
- Red banner: plain-language reason + raw remark. Carousel + caption read-only. Bottom bar: [Retry now] · [Reschedule] · [Cancel].

10. LOADING / FAILED THUMBNAILS
- "slide 2 · loading…" placeholders; failed: "slide did not load" + grey error + "retry".

11. FOOTER
- "review build 2026-09-09.a · drop is free · reroll is $0.24 · approved posts publish themselves".
