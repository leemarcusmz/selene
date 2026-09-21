# Selene Dreams — page redesign audit
Version 1.0 · 2026-09-09 · reviewed against PAGE-REDESIGN-BRIEF.md v1.0
Inputs: "Selene Dreams Research Picks" mockup (PNG) · "Selene Dreams Post Review 2a" (PDF)

## Changelog
- 1.0 (2026-09-09) — first audit of round-1 designs.

## PICKER — covered
Rule chips · prompt-slot meter · name field at top · live count · clear all · filters ·
rank badge · stat pills · caption + rationale split · open original · per-image order
badges + "→ prompt NN" · per-post "n of 5" dots.

## PICKER — missing states / elements
1. Overflow (16+): gold "next wk" badge, meter full, count line "· N saved for next week".
2. Zoom / lightbox on every tile (required).
3. Expired image: "recovering…" and "image expired" tile states.
4. Week-locked view: "This week is picked — <name> chose posts …".
5. Post-submit view: "You got it · N image sets saved for next week".
6. Lost-the-race error → reload to locked view.
7. Shelf rows ("Saved from earlier weeks", dashed cream) — distinct from
8. Topped-up rows ("held over from <week>" gold tag).
9. 6th-click behaviour on a post (recommend: remaining tiles disabled + tooltip).
10. Build-stamp footer.
11. Mobile layout (none shown).

## PICKER — unclear
- "2 held over from last week": chosen images from shelf rows, or shelf rows on page?
- Explicit per-tile "save for later" removed — intentional? Auto-overflow ≠ "want it, not in my 15".
- Filter chips (silk/linen/…) must be generated from the week's data.

## REVIEW — covered
Sidebar queue · calendar + legend · cadence-aware date picker defaulting to next open slot
(improvement) · final-order strip · drop/undo · per-slide grid · caption · corrected footer.

## REVIEW — missing states / elements
1. Reroll: location ("···"?), $0.24, "attempt n of 2", confirm, post-reroll "regenerating"
   state in sidebar (post leaves the feed).
2. Reject box with mandatory reason.
3. Scheduled/failed management: Cancel, Retry, "PUBLISH FAILED — <remark>". Where?
4. Cover label on first thumb; cover-changed warning.
5. Caption QA remark line.
6. Post-approve state (toast, sidebar update, calendar dot).
7. Empty state; thumbnail loading + failed-to-load placeholders.
8. Manual post-URL → col O (for hand-posted rows). Suggest "···" on a published day.
9. Mobile layout — this page is used on a phone. HTML5 DnD does not work on iOS Safari;
   need pointer-event DnD or keep ◀ ▶ fallback.

## REVIEW — unclear
- "Taken" dots imply one post per slot; nothing enforces that today. Enforce or allow stacking?
- "Awaiting approval" on the calendar — unapproved posts have no date. Proposed default?
- Non-cadence days selectable?
- Switching posts with unsaved caption edits — discard / keep / warn?
- Confirm "···" is per-slide (reroll one slide), not per-post.

## Buildability
Both fit Apps Script HtmlService. Calendar needs J/K/L for all rows + month nav — one read.
Only real risk: drag-and-drop on phone.

## Decisions needed before round 2
1. Picker: desktop-only or must work on phone?
2. Review: where does a Hold/failed post get handled?
