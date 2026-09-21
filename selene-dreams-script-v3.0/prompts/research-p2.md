<!-- VERSION: 2026-08-19.v3 — comment mining RE-ENABLED (run-scoped token; schema verified live 2026-08-19) -->
# PHASE 2 of 4 — captions and buyer objections

Phase 1's raw data is at `{step1_file}` — read it first, especially the TOP POSTS FOR PHASE 2 section.

## A. Captions (POSTS path)
Call POSTS with `fields=url,caption` and record the captions of the top posts verbatim.

## B. Comment mining
Engagement counts say something worked; comments say WHY, and what stops people buying.

Use the URLs under TOP POSTS FOR PHASE 2 in {step1_file} — **maximum 12, this cap is a cost control, never exceed it** (12 posts x 20 comments ~ 240 results ~ US$0.65).

This is the ONE POST request you are permitted to make. It uses the RUN-scoped token (actor runs), NOT the read-only token used everywhere else — do not swap them:

```
curl -s -X POST "https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items?token={apify_run_token}&format=json&clean=true&cb=<random>" \
  -H "Content-Type: application/json" \
  -d '{{"directUrls":["<url1>","<url2>"],"resultsType":"comments","resultsLimit":20,"addParentData":false}}'
```

SCHEMA VERIFIED 2026-08-19: this input returns an array of comment objects with `postUrl`, `text`, `ownerUsername`, `timestamp`, `likesCount`. If the call nonetheless errors, returns zero items, or returns post objects instead of comments: retry ONCE, then SKIP comment mining and record exactly what the API returned in COMMENT MINING STATUS. Do not try other actors, do not improvise endpoints, do not spend more credit. **This step must never fail the week.**

Classify EVERY comment returned as one of: PURCHASE-INTENT / OBJECTION / CARE-QUESTION / SIZING-FIT / PRICE / PRAISE / TAG-A-FRIEND / SPAM-BOT. (Bare-emoji comments are PRAISE unless context says otherwise.)

Write `{out_file}`:

```
## CAPTIONS
<url | caption verbatim, one per line>

## COMMENT INTENT
<per brand: class counts>

## OBJECTIONS (verbatim)
<the 5 strongest, each: brand | quote>

## PURCHASE INTENT (verbatim)
<the 3 strongest, each: brand | quote>

## COMMENT MINING STATUS
<worked, or exactly what the API returned and what you tried>
```

Objections are the highest-value output of the week: each recurring one is a content pillar Selene can answer while competitors ignore it. Then print a two-line summary and stop.
