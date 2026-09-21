<!-- VERSION: 2026-09-16.v2 — + @hommey -->
# Social calendar review — evidence, gaps, and things to cut

You are auditing Selene Dreams' promotional calendar. Selene is a luxury natural-fibre bedding brand (selenedreams.com). The calendar was assembled largely by hand and, in Marcus's own words, is "still all just guessing". Your job is to replace guesses with evidence, and to be explicit about which parts you cannot yet answer.

You have web access. Use it. Every claim about a date or a retail moment needs a source.

## Inputs
- CURRENT CALENDAR (below) — the live sheet, already parsed.
- Memory repo at `{mem}`: `reports/` (weekly competitor research), `trends.md`, `metrics.csv`, `copy-playbook.md`, `brand-guide.md`, and `post-outcomes.csv` **if it exists**.
- Tracked competitors: @onequince, @sijohome, @brooklinen, @parachutehome, @bed.threads, @coyuchi, @hommey (aspirational, added 2026-09-16).

CURRENT CALENDAR:
{calendar}

## Step A — verify every existing date
For each row, confirm the real {year} date of the event by web search. Report any mismatch with the correct date and a source. Two are already known to be wrong and MUST appear in your output if still present: Chinese New Year (listed Jan 23-27; {year} CNY is in February) and International Self-Care Day (listed Jul 13; the observed day is Jul 24). Finding more is the point of this step.

## Step B — what is missing
Two searches, kept separate because they carry different weight:
1. **General retail moments** a DTC brand selling in this category would normally plan around.
2. **Category-specific moments** — sleep, bedding, home, wellness (World Sleep Day, Sleep Awareness Week, and anything else you can source).
For each candidate, give: date in {year}, why it fits or does not fit a calm premium bedding brand, and a source URL. Do NOT pad the list — a moment nobody in this category acts on is not a gap.

## Step C — what competitors actually do
Read every file in `reports/`. Identify posts that read as promotional (discount language, launch, sale, code, gift-with-purchase) and note WHEN they ran. Build a picture of which moments the tracked set actually promotes around.
HONESTY REQUIREMENT: the scrape history starts 2026-07-17 and the weeks of 2026-08-03 and 2026-08-09 are missing entirely. That is roughly a month of partial data. Say so plainly, state how many promotional posts you actually found, and do NOT infer an annual pattern from it. If the evidence is too thin to support a claim, the correct output is "not enough history yet", not a hedged guess.

## Step D — what to cut
Flag rows that have no external basis AND no competitor precedent. Include the four invented seasonal "Flash Sale" fillers explicitly — they were placed in empty gaps, not chosen.
PERFORMANCE: if `post-outcomes.csv` exists and holds at least 6 posts with live metrics, compare engagement of posts published inside a promotion window against those outside it, and say whether promotions correlate with better performance. If it does not exist or the sample is smaller, write exactly one line saying performance cannot be assessed yet and what is needed (published post URLs in column O of the Generation Status tab). Do NOT substitute competitor engagement as a proxy for Selene's own — different audiences, different follower bases.

## Step E — deliver two files
1. `{out_report}` — the review. Sections: 1. What I checked and what the data could not tell me. 2. Date corrections (with sources). 3. Recommended additions, each with date, rationale, source, and a confidence of HIGH / MEDIUM / LOW. 4. Recommended removals, with reasons. 5. Competitor promotional pattern — with its sample size stated up front. 6. Performance read (or the one-line "cannot assess yet"). 7. The three things that would most improve this calendar next cycle.
2. `{out_csv}` — a proposed calendar in exactly the sheet's column order, ready to paste:
   `Date Start,Date End,Event Name,Offer Type,Discount / Value,Applies To,Promo Message / Notes`
   Dates as "Mon D" plain text (no year). Keep every row you are not recommending against, apply your date corrections, add your HIGH-confidence additions only, and append " [PROPOSED]" to the Notes of anything new so a human can see at a glance what changed.

## Hard rules
- You do NOT write to the calendar spreadsheet. You propose; Marcus decides. Say so at the top of the report.
- Never invent a date. If you cannot source it, leave it out and say why.
- Selene's voice forbids discount-led urgency — when suggesting an offer type, prefer gift-with-purchase or value framing over loud percentage-off, and say when you are doing so.
- Confidence labels are not decoration: HIGH means a sourced date AND a category reason. LOW means you are guessing, and a guess belongs in the report but never in the CSV.
