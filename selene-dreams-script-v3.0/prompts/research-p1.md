<!-- VERSION: 2026-08-17.v2 — recency gate on TOP POSTS + stale-post listing in DATA NOTES -->
# PHASE 1 of 4 — pull the week's data

Three calls, back-to-back. These are DIFFERENT API paths, so no spacing is needed between them.

1. **POSTS** with `fields=ownerUsername,type,likesCount,commentsCount,videoViewCount,timestamp,url`
2. **STATS** with `fields=username,followersCount,followsCount,postsCount,private,verified`
3. **HASHTAGS** with `fields=ownerUsername,type,likesCount,commentsCount,videoViewCount,timestamp,url,caption`

Write EVERYTHING you receive to `{out_file}` as plain text, in this structure:

```
## STATS
<one line per item, verbatim: username | followersCount | followsCount | postsCount | private | verified>
(if selenedreams_official has private:true, add a line: PRIVATE ACCOUNT WARNING)

## POSTS (total: N)
<one line per item: ownerUsername | type | likesCount | commentsCount | videoViewCount | timestamp | url>
<then, any items carrying an error field: ERROR | inputUrl>

## HASHTAGS (total: N)
<one line per item: ownerUsername | type | likesCount | commentsCount | videoViewCount | timestamp | url | caption first 150 chars on one line>

## TOP POSTS FOR PHASE 2
<the top 3 posts by engagement for EACH of @onequince, @sijohome, @brooklinen, @parachutehome — one URL per line, max 12 lines, nothing else. RECENCY GATE: only posts whose timestamp is within 45 days of today are eligible here.>

## DATA NOTES
<which profiles or tags are missing or errored; whether counts look plausible; anything that looks like cached/stale data>
<STALE POSTS: list every POSTS item whose timestamp is MORE than 45 days before today, as `username | timestamp | url`. The scrape is configured for a 45-day window but older pinned/evergreen posts leak through (a 2025-03-29 brooklinen post appeared on 2026-08-17). Later phases must exclude these from all rankings and trend claims.>
```

DO NOT analyze, rank, or interpret yet — later phases do that from these raw lines, and they can only be as honest as this dump is complete. Do not skip or summarize items. If a call fails, retry it ONCE, then record the failure in DATA NOTES and continue with what you have.

When the file is written, print a two-line summary to stdout and stop.
