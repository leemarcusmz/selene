---
name: selene-caption-writer
description: "Generate the Instagram caption and per-image alt text for a finished Selene Dreams post (one Generation Queue row / one carousel), following Selene's locked caption format, with self-improving hashtag and copy choices. Use whenever Marcus asks for captions, hashtags, or alt text for Selene posts — trigger on phrases like \"write the caption\", \"caption and alt text for row N\", \"selene captions\", \"alt text for these images\", or when he shares freshly generated Selene product images and wants them ready to post. metadata: type: workflow"
---

# Selene Dreams Caption Writer

Produces two outputs for a finished post: ONE caption per post (per Generation Queue row), and ONE alt text per image. Runs after image generation — alt text must describe the actual images, never the prompts.

## Step 1: Gather inputs

Need three things before writing:
1. **The generated images** — you must actually SEE every image. Sources in preference order: files Marcus attaches; the row's Output Folder / Image URLs in the Generation Queue sheet (stage via device bridge or view via browser); or ask Marcus to paste them. Do not write alt text for an image you have not seen.
2. **Product context** — Fabric / Product Type / Variant from the queue row, plus any special info Marcus gives (sale, launch, restock, collab). If he references a row number, read the row.
3. **The learning file** — see "Self-improvement loop" below. If unavailable, proceed without it and say so in one line.
4. **The hooks library** — `hooks-library.md` in the same repo: use Proven hook patterns for taglines and opening lines (filtered through Selene's calm voice), Testing patterns sparingly, and note in the playbook entry which hook type each caption used so performance can be attributed.
5. **The keyword bank** — `keyword-bank.md` in the same repo (same fallbacks). This is the shared SEO vocabulary: use ACTIVE transactional terms front-loaded in the tagline/body for the product at hand, TESTING terms sparingly, never RETIRED terms, and obey its attribute-vocabulary rules (never claim specs/certifications the website doesn't). If a keyword you want isn't in the bank, you may use it, but add it to the bank's Candidates section when you log the entry.

## Step 2: Research the 3 variable hashtags

The caption always carries exactly 5 hashtags: #fyp and #explorepage✨ are fixed; the other 3 are chosen fresh every run. Pick: one broad-reach tag, one product/category tag, one niche/intent tag. Ground the choice in evidence, not habit: check the learning file for tags that correlated with above-median reach on past Selene posts, and do a quick web search for currently active bedding/sleep/home hashtags when the product or season suggests the old picks may be stale. Prefer tags a real buyer would search over vanity tags. Never reuse a 3-tag combo flagged as underperforming in the learning file.

EXPERIMENT SLOT: treat the niche/intent tag position as a deliberate experiment slot. Rotate it consciously across posts (don't repeat the same niche tag twice in a row), and record in the learning file which slot value each post used — this is what lets the monthly deep-dive attribute hashtag effects with actual evidence instead of vibes. The broad and product slots stay stable so the experiment is clean.

## Step 3: Write the caption (LOCKED FORMAT)

Format exactly as below. Use a literal period on its own line as each separator.

- Line 1: Short tagline visible before "more" is tapped — punchy, benefit-led, ends with ONE relevant emoji.
- Line 2: .
- Line 3: Expanded body — 2 to 4 sentences on the product/message. Weave in natural SEO keywords a buyer would search (e.g. silk pillowcase, hypoallergenic, cooling, hair, skin, sleep) without keyword-stuffing. If special info was provided, incorporate it clearly here.
- Line 4: .
- Line 5: Exactly 5 hashtags on one line. #fyp and #explorepage✨ are ALWAYS 2 of the 5.

Caption SEO notes: front-load the most important keyword in the first 1–2 lines (Instagram weights early text); keep the tagline scannable; keep the body natural enough that it reads like a person, not a search query.

Example of correct output:

```
Get good sleep with Selene ❤️
.
Smooth, cooling, and beautifully gentle on skin and hair—our 100% Mulberry Silk pillowcase elevates your nightly routine. Naturally hypoallergenic and breathable, silk helps minimize friction and sleep creases, keeping hair shinier and skin smoother.
.
#fyp #explorepage✨ #silkpillowcase #sleep #comfortzone
```

The five-line skeleton, the literal-period separators, the 5-hashtag rule, and the two fixed hashtags are non-negotiable. Everything inside the lines (tagline angle, body copy, keyword choices, the 3 variable hashtags) is where quality lives and where the learning file should shape your choices — e.g. if question-style taglines or texture-led bodies have outperformed for Selene, lean that way; the format stays identical while the writing gets smarter.

## Step 4: Write alt text (one block per image, in order)

For EACH image, in order, produce a separate block labeled Image 1, Image 2, etc. Each alt text:

- Literally describes what is in the image (subject, setting, colors, texture, action) so it is accessible to screen-reader users and indexable by search.
- Is 1 to 2 sentences, concrete and specific.
- Naturally includes 1 to 2 relevant SEO keywords (e.g. mulberry silk pillowcase, satin sleep set) only where they genuinely describe the image — never force them.
- Never starts with "Image of" or "Photo of."

Self-optimization for alt text: favor concrete sensory nouns (weave, drape, slub, sheen) over vague adjectives (beautiful, cozy); name the actual product and color variant when visible; lead with the subject, not the room. Record in the learning file any wording patterns that the weekly research shows correlating with better reach, and apply them.

## Step 5: Present, revise, deliver

Show the caption and all alt text blocks in chat. Ask Marcus: approve / tweak specific lines / regenerate hashtags only. On approval, write to the **"Generated Caption" tab** of the Content Generation Queue sheet (gid 933825248). Never write to the sheet without approval.

### Where captions live (changed 2026-07-22)
Captions and alt text are NO LONGER stored in the Generation Queue's columns W/X. They go in the dedicated **"Generated Caption"** tab, one row per post, columns:
`A #` (matches the Generation Queue # so Marcus knows which row) · `B Caption` (one per row, the full multi-line caption) · `C–G Alt Text Img 1–5` (one alt text per image, in order; leave unused columns blank) · `H Remark(s)` (flags: AI artifacts, a person in a no-people shot, color inconsistencies, etc.).

### How to write it (the reliable method — READ THIS, the obvious ways fail)
Writing multi-line captions into a cell via the browser is finicky. Confirmed on 2026-07-22:
- Synthetic in-cell line-break keys DO NOT work: `cmd+Return`, `alt+Return`, `ctrl+Return`, `alt+Enter` all either no-op or commit early. Do not rely on them.
- Typing a `=CHAR(10)`-style formula DOES NOT work: Sheets auto-closes quotes and mangles it.
- `navigator.clipboard.writeText` and Cmd+V paste FAIL on a background tab ("document is not focused") — and the scheduled sheet tab is usually backgrounded behind whatever Marcus is doing.

The method that works: build a TSV/CSV block (one row per post: `#\t"caption"\talt1\t…\talt5\tremark`, with the caption field RFC4180-quoted so its internal newlines stay in-cell), put it on the OS clipboard with a temporary textarea + `document.execCommand('copy')` (this works even without focus), then paste it in a **foreground** Sheets tab. To guarantee foreground: open the sheet in a NEW tab (new tabs open focused), if it loads a "poor connection / last synced version" banner click Force reload, select the target cell via the Name Box, then `cmd+v`. Verify with a screenshot that captions landed multi-line in one cell and columns didn't shift. Append at the first empty row below the last `#`; never overwrite an existing row for the same `#` without checking with Marcus.

Also offer, if Marcus prefers, a text file per post delivered in chat as a lightweight alternative.

## Self-improvement loop

The learning file is `copy-playbook.md` and the keyword bank is `keyword-bank.md`, both in the `selene-ig-memory` GitHub repo (fallback: `_00. Memory/_Ventures/Selene Dreams/IG Research/copy-playbook.md` on the Mac; if neither is reachable, skip gracefully).

- READ it before writing: past captions with their post URLs, hashtag combos used, engagement outcomes (filled in by the weekly research agent's own-brand check), and accumulated style learnings.
- WRITE to it after approval: date, product, the final tagline, the 3 variable hashtags, alt-text keyword choices, and the post URL once known. Append, never overwrite history.
- The weekly research agent annotates these entries with engagement data; over weeks this is what makes hashtag and copy choices genuinely evidence-based rather than guessed.

## Hard rules

- Never break the caption skeleton or the two fixed hashtags.
- Never invent engagement claims — if the learning file is empty, choices are "best judgment + current research," and say so.
- Alt text only for images actually seen.
- Captions/alt text go in the "Generated Caption" tab (# / Caption / Alt Text Img 1–5 / Remark(s)), keyed by the Generation Queue #. Not columns W/X.
- Nothing is posted anywhere by this skill; it produces copy for Marcus to publish.
