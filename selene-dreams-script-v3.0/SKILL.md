---
name: selene-prompt-writer
description: "Generate Selene Dreams AI image prompts from reference images and append them to the Generation Queue Google Sheet. Use when Marcus wants to create new bedding product prompts — trigger on phrases like \"generate Selene prompts\", \"make prompts for Selene\", \"write prompts from these references\", when he uploads reference images and mentions Selene Dreams, OR when he picks numbered posts from a weekly IG research report (e.g. \"use 2, 5 and 7\", \"make prompts from this week's shortlist\") — that invokes the report fast path. metadata: type: workflow"
---

# Selene Dreams Prompt Writer

This skill walks Marcus through creating AI image prompts for the Selene Dreams bedding brand, then appends them to the Generation Queue Google Sheet.

## When to trigger

Activate when Marcus:
- Says "generate Selene prompts" or similar
- Uploads reference images and mentions Selene Dreams
- Asks to write prompts for a specific Selene product
- References the AI Generation Flow

## The flow — step by step

There are two entry paths. Use the REPORT FAST PATH when Marcus references a weekly IG research report and post numbers (e.g. "use 2, 5 and 7"); use the CLASSIC PATH when he brings his own reference images. Both paths converge at prompt generation (Step 5).

## Report fast path (weekly research shortlist)

**WEEK LOCK (added 2026-07-23):** post selection is now first-come-first-served across Marcus's team via the "Selene Picks" web page, recorded in the sheet's "Weekly Picks" tab. Before running this fast path, check that tab (via the Drive connector or browser) for a row matching the current week's shortlist: if the week is already picked, tell Marcus who picked what and STOP — only proceed if he explicitly says to override or add. If Marcus picks via chat and the week is unlocked, proceed normally AND append a Weekly Picks row (Week = shortlist date, Picker = "Marcus (chat)", Posts, Slide choices, timestamp, status) using the available sheet-write path, so the web page locks for teammates.

The weekly research agent delivers `research-report-YYYY-MM-DD.md` with a numbered REFERENCE SHORTLIST. Each entry carries: brand, post URL, type (CAROUSEL / IMAGE / VIDEO-cover), all reference image URLs (every slide for carousels), and a suggested Selene product mapping (Fabric / Product Type / Variant). When Marcus picks numbers, that report already contains almost everything the classic path would ask for — so don't re-ask; confirm.

### F1: Locate the report

In priority order: a report file attached in this chat; the newest `research-report-*.md` in `_00. Memory/_Ventures/Selene Dreams/IG Research/` on his Mac (stage it via the device bridge); or the session where the report was delivered. If none found, tell Marcus and ask him to attach it.

### F2: Extract the chosen entries

**MAX 5 POSTS PER SELECTION (rule set 2026-07-22).** If Marcus (or a teammate) picks more than 5 numbers, do not proceed — show the list and ask which 5 to keep. The cap controls generation cost and keeps each batch reviewable.

For each number picked (≤5), pull from the shortlist: post URL, type, image URLs (in slide order), and the suggested product mapping. Validate the mapping against the catalog in Steps 1–3 below — if a suggested combination is not a valid Fabric/Product/Variant combo, flag it and ask instead of silently using it.

### F3: One confirmation pass (single AskUserQuestion, not one per attribute)

Show a compact summary — "Post 2 (Quince carousel, 4 slides) → Sateen Duvet Set, Driftwood" — and ask one question per selected post with options: "Confirm mapping" / the 1–2 most plausible alternative products given the image content / "Let me choose step-by-step". Only fall back to the classic Step 1→2→3 sequence for posts where he picks the last option. The point of the fast path is that his taste already acted at selection time; don't make him re-answer what the report already knows.

**This confirmation IS the approval for the whole fast path.** Once Marcus confirms the mappings here, do not gate again: generate the prompts and append them to the Generation Queue sheet automatically (F5 → F6 → append). Show the prompts in chat as you write them to the sheet so he can see what went in — and if he replies asking to change one, edit that prompt and update the same row rather than adding a new one. The classic path's Step 6 approval gate does NOT apply to the fast path.

### F4: Get the images in front of your eyes

You need to actually SEE each reference image to write a faithful prompt — never write prompts from the caption or your imagination of the URL. Ways to see them, in preference order: (1) open each image URL in a Chrome tab via the browser tools and view it (screenshot the tab); (2) ask Marcus to paste the images into the chat if the browser isn't connected; (3) if a CDN URL has expired (they are signed and die after some weeks), tell Marcus which one and ask him to open the post URL and screenshot the slide. Do not proceed to prompt writing for an image you have not seen.

### F5: Carousel → one sheet row (MAX 3 PROMPTS PER ROW)

A carousel reference maps naturally onto ONE Generation Queue row: up to 3 slides → Prompt 1–3 columns. **Hard cap: 3 prompts per row, to save generation credits.** Generate one prompt per used slide (same room/mood family across slides so the generated carousel feels coherent — vary framing and detail, not the whole world). A single-image reference produces one prompt in an otherwise normal row.

**If a chosen post has MORE than 3 images (rule updated 2026-07-22): the USER chooses which 3 — do not auto-pick.** During the F3 confirmation pass, for any such post ask via AskUserQuestion (multiSelect) which slides to generate from, labeling each slide by number with a one-line visual description (e.g. "Slide 2 — overhead flat-lay of pillowcase"). If they pick more than 3, ask them to trim to 3. Only if they explicitly answer "you choose" may you select the 3 strongest, saying which and why.

Never fill Prompt 4 or Prompt 5 — leave those columns empty. If Marcus explicitly asks for more than 3 prompts for a specific row, warn him it costs extra credits and only exceed the cap on his explicit say-so. (Note 2026-07-22: the queue's Reference Image columns were deleted — prompts are the only thing written per slide; reference URLs live in the report/selections log, not the sheet.)

### F6: Log the selection (learning step — do not skip)

Marcus's picks AND passes are the pipeline's taste signal. After his selection is confirmed, append an entry to `selections.md` in the selene-ig-memory GitHub repo (clone URL and token are in project memory under selene-ig-research-agent; fallback: `_00. Memory/_Ventures/Selene Dreams/IG Research/selections.md` on the Mac; if neither reachable, skip with a one-line note). Entry format: date, report date, PICKED: numbers + post URLs + one word on why if he said, PASSED: the remaining shortlist numbers + post URLs. Commit and push ("Log selection YYYY-MM-DD"). The weekly research agent reads this to learn his visual taste — every unlogged week is a wasted training signal.

Then continue at Step 5 (prompt generation) and go STRAIGHT to Step 7 (append to sheet) — in the fast path, skip Step 6: Marcus already approved at F3, so the prompts are written to the sheet automatically without asking again. (Reference image URLs are no longer written to the sheet — those columns were removed 2026-07-22; they stay in the selections log only.)

## Classic path (Marcus brings reference images)

Follow these steps in order. Don't skip ahead. Ask one question at a time using AskUserQuestion where a discrete choice is required.

### Step 1: Fabric selection

Ask Marcus which Fabric using AskUserQuestion. Options:

- Cooling
- Gauze
- Linen
- Percale
- Sateen
- Silk
- Tencel

### Step 2: Product Type selection

Based on the Fabric chosen, present ONLY the valid Product Types using AskUserQuestion:

- Cooling → Blanket
- Gauze → Blanket
- Linen → Duvet Set, Sheet Set
- Percale → Duvet Set, Sheet Set
- Sateen → Duvet Set, Sheet Set
- Silk → Eye Mask, Pillow Case
- Tencel → Duvet Set, Sheet Set

If the Fabric has only one Product Type (Cooling, Gauze), you can auto-select and confirm rather than asking.

### Step 3: Variant selection

Based on Fabric + Product Type, present ONLY the valid Variants using AskUserQuestion:

- Cooling / Blanket → Cream White, Ocean Breeze, Silver Mist
- Gauze / Blanket → Alabaster White, Shadow Gray, Soft Maple
- Linen / Duvet Set → Alabaster White, Desert Sand, Stone Sage, Terracotta Blush
- Linen / Sheet Set → Alabaster White, Desert Sand, Stone Sage, Terracotta Blush
- Percale / Duvet Set → Ash Gray, Desert Sand, Herb Sage, Icy White
- Percale / Sheet Set → Ash Gray, Desert Sand, Herb Sage, Icy White
- Sateen / Duvet Set → Driftwood, Icy White, Ocean Breeze
- Sateen / Sheet Set → Driftwood, Icy White, Ocean Breeze
- Silk / Eye Mask → Alabaster White, Olive Sage, Pewter Gray, Warm Taupe
- Silk / Pillow Case → Alabaster White, Olive Sage, Pewter Gray, Warm Taupe
- Tencel / Duvet Set → Deep Ocean, Dove Gray, Frost White, Stone Taupe
- Tencel / Sheet Set → Deep Ocean, Dove Gray, Frost White, Stone Taupe

### Step 4: Reference images

Ask Marcus to provide reference images. Accept either:
- Direct image uploads in the chat (up to 3 images)
- Image URLs pasted into the chat (fetch via web_fetch if needed)
- Any mix of the two

Confirm how many references received before proceeding. If more than 3, only use the 3 strongest (or the first 3 if quality is comparable) and note which are being skipped — the row cap is 3 prompts (see F5 rule; it applies to both paths).

### Step 5: Prompt generation

For each reference image (max 3 per row), generate ONE prompt following the rules in the "Prompt writing rules" section below. Analyze the reference image directly using vision — describe what's in it, then adapt it into a Selene Dreams product prompt.

Number the prompts clearly:

```
Prompt 1: [full prompt text]

Prompt 2: [full prompt text]

Prompt 3: [full prompt text]
```

Present these in the chat for Marcus to review.

### Step 6: Approval (classic path only — fast path skips this)

After displaying the prompts, ask Marcus (using AskUserQuestion):

- Approve — write to sheet
- Edit a prompt — I'll ask which one and re-write
- Regenerate all — start over from the same images
- Cancel — abort

If he picks "Edit a prompt", ask which prompt number, ask what to change, regenerate just that one, show the updated set, and ask again.

If he picks "Regenerate all", re-run Step 5 with the same images.

### Step 7: Append to sheet

On approval (classic path) or immediately after prompt generation (fast path), append the row. **Max 3 prompts per row — never pass more than 3 entries in the prompts JSON.**

Pick the write path by where this session is running (see "Choosing the write path" below). The three options, in order of preference for the situation:

**A. Local Cowork session (running on Marcus's Mac) — use append_row.py.** Use the Bash tool to invoke it:

```
python3 "/Users/marcuslee/Desktop/_Claud/Work Projects/Selene Dreams/AI Generation Flow/selene-dreams-script-v3.0/append_row.py" \
  --fabric "FABRIC_HERE" \
  --product-type "PRODUCT_TYPE_HERE" \
  --variant "VARIANT_HERE" \
  --prompts 'JSON_ARRAY_HERE'
```

Where JSON_ARRAY_HERE is a JSON array of the approved prompts, e.g.:

```
'[{"prompt":"First prompt text..."},{"prompt":"Second prompt text..."}]'
```

Important:
- Wrap the prompts JSON in SINGLE quotes to preserve double quotes inside
- Escape any single quotes within prompt text if needed
- Year and Month default to current — no need to pass them unless Marcus specified otherwise

Read the script's output. If it says "SUCCESS: Row N added", confirm to Marcus:

"Done — row N added to the Generation Queue. Review it in the Sheet, then flip Status to 'Ready' when you want to trigger image generation."

If the script errors, show the error to Marcus and offer to try again.

**B. Cloud session with Marcus's Mac + Chrome online — use browser automation.** append_row.py cannot run from a cloud Cowork session (the script lives on Marcus's Mac, and the sandbox has no network route to Google's APIs). If the Claude-in-Chrome browser tools are connected, open the Generation Queue sheet in Chrome and enter the row directly: jump with the Name Box, Tab between cells, cmd+Return for in-cell line breaks (see project memory selene-generation-queue for the exact mechanics). This is the fast path — the row appears in seconds.

**C. Cloud session with no browser (Mac closed / Chrome offline) — use the GitHub queue bridge.** This is the fallback that works with Marcus's Mac completely off. Commit a queue file to the `selene-ig-memory` repo (same repo + token the research/caption agents use — clone URL and token in project memory under selene-ig-research-agent); an Apps Script bound to the sheet polls the `queue/` folder every ~5 minutes and appends the row on Google's side. Steps:

1. `git clone https://x-access-token:<TOKEN>@github.com/leemarcusmz/selene-ig-memory.git /tmp/mem` (or reuse an existing clone).
2. `mkdir -p /tmp/mem/queue` and write a file named `YYYY-MM-DDTHHMM-<fabric-variant-slug>.json` (timestamp-first so files process in order; make the name unique). Contents:

```json
{
  "year": "2026",
  "month": "July",
  "fabric": "Sateen",
  "productType": "Duvet Set",
  "variant": "Driftwood",
  "prompts": ["First prompt text...", "Second prompt text...", "Third prompt text..."]
}
```

   `prompts` MUST be ≤3 (the bridge also truncates to 3 defensively). `year`/`month` optional — the bridge defaults to current. (referenceImages was dropped 2026-07-22 — those queue columns no longer exist.)
3. `git add queue/ && git commit -m "Queue row YYYY-MM-DD <product>" && git push` (one retry on failure).
4. Tell Marcus: "Your Mac was off, so I queued the row via GitHub — it'll appear in the Generation Queue within ~5 minutes. Nothing else needed." Do NOT stop and ask; the queue commit IS the append under the auto-append promise.

**Choosing the write path:** local Mac session → A. Cloud session → try B (browser) first; if the browser isn't connected, fall to C (queue) automatically. Never block waiting for the Mac to come online — B and C together always give a working path. If a git/push step in C fails after one retry, tell Marcus the prompts are ready but the queue push failed, and paste the JSON so nothing is lost.

## Prompt writing rules

When generating each prompt from a reference image:

1. **Analyze the reference** — describe the scene, lighting, composition, mood, camera angle, and any props/setting details.

2. **Swap in the Selene Dreams product** — replace whatever product is in the reference (if any) with the Selene Dreams [Fabric] [Product Type] in [Variant] color. If the reference has no bedding, add the product to the scene naturally.

3. **Modify some details** — don't produce a duplicate of the reference. Tweak specifics: change some props, shift the color palette slightly, adjust the time of day, alter the framing. The goal is "same vibe, different execution."

4. **Structure the output prompt** — write for Nano Banana Pro. Roughly this structure:

```
[Scene setting and mood]. The Selene Dreams [Fabric] [Product Type] in [Variant] is [placement description]. [Lighting details]. [Two or three supporting scene details]. [What's NOT in the shot — no people, no clutter, no other bedding items]. Photorealistic, [camera angle], [depth of field], [palette].

The product in the final image must be the exact Selene Dreams [Fabric] [Product Type] shown in the source photo — preserve its color, texture, weave, and pattern. Do not generate a different product.
```

5. **Length** — aim for 4–7 sentences per prompt. Long enough to be specific, short enough that Nano Banana Pro doesn't lose focus.

6. **Brand voice** — Selene Dreams is calm, elevated, natural. Prefer scandinavian, japandi, mediterranean, soft boho settings over maximalist or industrial. Prefer natural light over artificial. Prefer minimal styling over cluttered.

## Notes for Claude executing this skill

- Do not skip the step-by-step selection. Even if Marcus's initial message includes all the info (fabric + product + variant + images), still confirm each choice using AskUserQuestion so mistakes are caught early.
- If Marcus provides URLs instead of uploads, use web_fetch to retrieve the image first so you can analyze it.
- HARD CAP: 3 prompts per Generation Queue row, on both paths. Only exceed with Marcus's explicit instruction after warning about extra credits.
- Classic path: always show the final prompts in the chat BEFORE running append_row.py — never write to the sheet without explicit approval.
- Fast path: the F3 selection confirmation IS the approval. After it, generate prompts and append to the sheet automatically in the same run — show the prompts in chat alongside the append, but do not ask a second approval question. If Marcus requests a change afterwards, update the existing row.
- The append_row.py script requires `credentials.json` and `token.json` to be present in the v3 folder. If the script errors with an auth issue, tell Marcus to check that file exists and possibly delete `token.json` to re-auth.
