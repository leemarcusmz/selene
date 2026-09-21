<!-- VERSION: 2026-09-16.v6 — + @hommey in the tracked brand feeds -->
# PHASE 4 of 4 — analyse, self-criticise, publish

All the week's raw data is already collected. No further API calls of any kind.

INPUTS: `{step1_file}` (posts, stats, hashtags) · `{step2_file}` (captions, comments) · `{step3_file}` (image URLs). The memory repo is cloned at `{mem}`.

## Step A — read memory
`{mem}/brand-guide.md` FIRST — its photography rules and 12-point rubric govern every candidate decision; if it conflicts with anything else, it wins. Then `trends.md`, the 2-3 most recent `reports/`, `copy-playbook.md`, `keyword-bank.md`, `hooks-library.md`, `metrics.csv`, `selections.md`, `objections.md`, and — for the own-brand section — `post-outcomes.csv`, `generation-scores.csv` and `prompt-playbook.md`.

## Step B — analyse
- **RECENCY GATE (apply before any ranking)**: a post is eligible for rankings, "top post", "best this week", trend, hook-taxonomy and velocity claims ONLY if its timestamp is within 45 days of the pull date. Older items leak through the scrape (a 2025-03-29 brooklinen post appeared on 2026-08-17; a 5-week-old sijohome post was wrongly called "this week's best" on 2026-08-10). Check the STALE POSTS list in the phase-1 DATA NOTES and exclude those URLs. Out-of-window posts may be cited ONLY as explicitly-labelled historical context, never as current performance. Say in the data notes how many you excluded.
- **Metrics**: rank by engagement rate (interactions ÷ followers; show raw + rate), the two tiers in separate lists. Cadence and best times in HKT. Format mix. Caption features. Velocity flags — but never for the three brands added 2026-08-12.
- **Hook taxonomy**: classify every top post (tracked brands AND hashtag posts) as QUESTION / BENEFIT-CLAIM / SCARCITY-RESTOCK / MOMENT-JACK / EDUCATION / HUMOR / SOCIAL-PROOF / TRANSFORMATION. Which types are rising or fading versus recent weeks.
- **Hashtag frontier**: accounts and aesthetics recurring across tags that the 6 tracked brands have not adopted.
- **Own brand**: engagement rate vs market, follower growth vs metrics.csv, and attribution — match scraped own captions to copy-playbook.md. THEN, using post-outcomes.csv + generation-scores.csv: do higher rubric scores correspond to better performance, or not? Say so plainly either way — a rubric that does not predict performance is worth knowing. Name rows whose post URL is missing from the sheet. **If fewer than 6 posts have both a QA score and metrics, state that the sample is too small and stop there — do not manufacture a correlation from four points.**
- **Keywords**: recurring commercial terms in top captions not already in keyword-bank.md.

## Step C — candidate pool (18-25)
Brand fit comes FIRST; engagement rate is only a tiebreaker.

(a) Apply brand-guide.md's instant-exclude list — giveaways/contests, dorm or back-to-school staging, busy commercial line-ups, urban/industrial settings, neon or saturated grades, meme-voice posts — regardless of engagement.

(a2) HARD REJECTS — these never enter the pool, whatever their engagement (added 2026-08-17, after a pool of 17 yielded only 2 on-brand references; the screener cut a laptop screenshot, a street billboard, a food flatlay and three meme cards):
  - **No bedding as the subject.** If bedding is absent, incidental, or merely the surface something else rests on (food, a laptop, a non-bedding product), reject. This is the most common junk pattern.
  - **Heavy-text graphics.** Ad creatives, infographics, "new arrival" launch cards, price/discount promos, testimonial cards — anything where typography rather than photography carries the frame.
  - **Meme-voice posts.** Listicle overlays, "me trying to..." captions, emoji-math cards, gradient text cards.
  - **Screenshots.** Phone screenshots, app or browser captures, screen-recording stills.
  - **Dark or "powerful" backgrounds.** Bedding on near-black or dark saturated grounds violates the never-dark-ground rule and has never survived screening.
  - **Saturated resort/tropical scenes.** They score deceptively close to the line on raw rubric points and have a poor historical pick rate — keep them below it.

(b) Estimate each candidate's fit against the 12-point rubric from caption language, account aesthetic and setting cues. You cannot view the images — say so, and score conservatively. Selene's world is bedding-in-nature, dusk/dawn light, film grain, serene and ethereal.

(c) SOURCE BALANCE — brand fit still decides ranking, but the pool must not be swallowed by the hashtag frontier:
  - **At least 8 entries must come from tracked brand feeds** (@onequince, @sijohome, @brooklinen, @parachutehome, @bed.threads, @coyuchi, @hommey). These are curated brand accounts; the hashtag frontier is unfiltered and its quality swings hard week to week.
  - Beyond that floor, let the pool skew to wherever the fit actually is — @bed.threads, @coyuchi, @hommey, #slowliving and #linenbedding will often out-score the direct competitors. For @hommey specifically, favour entries that show a FORMAT or HOOK move (how the post is built) over ones that are mainly a colour story — see the HOMMEY NOTE in the common brief.
  - If fewer than 8 tracked-brand posts clear the hard rejects, take all that do and SAY SO in the data notes. Never backfill the gap with hashtag posts that only just cleared.

(d) Each candidate's note must cite WHY it plausibly fits — which rubric qualities.

(e) Dedup against past shortlists and apply the selections.md taste model.

(g) UPCOMING PROMOTIONS — steer the product mapping, nothing else (added 2026-08-17). The lead time from this report to a published post is one to two weeks, so a reference chosen now should suit what is about to be promoted.

{calendar}

Use it like this: where two candidates fit the brand equally well, prefer the one whose suggested product maps to a promotion in the window, and say so in its note ("maps to Linen Duvet, on promo Sep 1-5"). Do NOT let a promotion pull an off-brand candidate into the pool — brand fit still decides, this is a tiebreaker. Do NOT write promotional or discount language anywhere: urgency and price-led voice are off-brand and the screener cuts them on sight. If the block above says the calendar could not be read, say that in the data notes rather than assuming there is nothing on.

(f) SIZE HONESTY — 18-25 is a target, not a quota. If fewer than 18 candidates survive (a) through (e), publish only those that did and open the CANDIDATE POOL section with one line stating how many qualified, how many were hard-rejected, and why the week was thin. A short honest pool is correct; padding it with material that will be cut at screening wastes the screener's budget and hands the team a shortlist of two.

## Step D — CRITIC PASS, before anything is written to memory
Launch a SUBAGENT with the Task tool (fresh context, general-purpose) and give it your draft report plus the raw lines from the input files. Its brief, verbatim:

"You are a skeptic reviewing a market research report. For EVERY factual claim, ranking, trend statement and recommended play, return a verdict: SUPPORTED (cite the raw data lines that establish it), WEAK (directionally arguable, but the sample is too small, the metric is confounded, or the comparison is unfair), or UNSUPPORTED (not derivable from this data at all). Assume the author over-read the data — your job is to find where. Pay particular attention to: (a) trends asserted from a single week of observation; (b) engagement comparisons across very different follower counts, or between the direct-competitor and aspirational tiers; (c) claims about brands whose scrape partially failed; (d) causal language where only correlation exists; (e) any number that does not reconcile with the raw lines; (f) recommendations that would be made regardless of what the data said. Return a list of {{claim, verdict, reason}}."

If the Task tool is unavailable, run the same review yourself as a separate clean pass, re-reading the RAW LINES rather than your own summary — never review your own prose against your own prose.

Then act: DELETE every UNSUPPORTED claim, rewrite WEAK ones with explicit hedging and the reason ("single week, n=4"), and record what was cut. A shorter honest report beats a longer confident one.

## Step E — write and push
In `{mem}`:

1. `reports/research-report-{week}.md` — sections: 1 Data notes · 2 Top performers per tier (raw + rate) · 3 Hook analysis with 2-3 verbatim standouts · 4 Hashtag frontier · 5 Cross-brand drivers, trend deltas, cadence/timing HKT, format mix · 6 Own-brand check · 7 Comment intent (counts, 5 verbatim objections, 3 verbatim purchase-intent, recurring vs new, and which objection Selene is best placed to answer — say plainly if mining failed) · 8 Candidate pool · 9 Recommended plays (max 5) · 10 Confidence — what the critic cut or hedged and what this week's data cannot support.
2. `candidates/candidates-{week}.json` (create the dir if absent) — complete, valid JSON:
`{{"week":"{week}","entries":[{{"n":1,"source":"@brand or #tag","type":"CAROUSEL|IMAGE|VIDEO-cover","postUrl":"https://...","concept":"one-line visual concept","caption":"the post's original caption, verbatim, from {step2_file} (empty string if not captured)","likes":269,"comments":12,"engagement":"269 likes · 12 cmts","product":{{"fabric":"...","productType":"...","variant":"..."}},"images":["slide url 1","..."]}}]}}`
Every image URL verbatim in slide order, from {step3_file}. `product` = one valid catalog combo:
Cooling Blanket: Cream White, Ocean Breeze, Silver Mist · Gauze Blanket: Alabaster White, Shadow Gray, Soft Maple · Linen Duvet/Sheet Set: Alabaster White, Desert Sand, Stone Sage, Terracotta Blush · Percale Duvet/Sheet Set: Ash Gray, Desert Sand, Herb Sage, Icy White · Sateen Duvet/Sheet Set: Driftwood, Icy White, Ocean Breeze · Silk Eye Mask/Pillow Case: Alabaster White, Olive Sage, Pewter Gray, Warm Taupe · Tencel Duvet/Sheet Set: Deep Ocean, Dove Gray, Frost White, Stone Taupe
3. Week entry at the TOP of `trends.md`, including the count of claims the critic cut or hedged.
4. `metrics.csv` — a row per brand (date,username,followersCount,followsCount,postsCount; create with header if absent).
5. `copy-playbook.md` attribution · `keyword-bank.md` Candidates section only · `objections.md` (create with a header if absent) — dated section with this week's classified objections and verbatim quotes, marking any that have now recurred 2+ weeks · `hooks-library.md` Observed section only (never touch Proven/Testing) · a `selections.md` stub if last week's picks are unlogged.

Then: `git add -A && git commit -m "Weekly research {week}" && git push` (one retry; report failure honestly).

Do NOT write the shortlist — the Mac visual screener views every image and produces it within the hour.

Finish with a 10-line plain-text summary to stdout: data status, top findings, candidate count, what the critic cut.
