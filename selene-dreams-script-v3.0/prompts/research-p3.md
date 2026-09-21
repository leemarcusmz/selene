<!-- VERSION: 2026-08-13.v1 -->
# PHASE 3 of 4 — image URLs for the candidate pool

Read `{step1_file}` (raw posts and hashtag items).

First decide, from the raw lines alone, a LONGLIST of 25-35 posts that could plausibly become carousel/image references for Selene. Prefer Sidecar/Image; Video only where a static cover is strong; no Reels. Err inclusive here — the next phase cuts, and the Mac visual screener cuts harder.

Then fetch their image URLs:

1. **POSTS path** with `fields=url,type,displayUrl,images` — for longlist entries that came from tracked brands.
2. **HASHTAGS path** with `fields=url,type,displayUrl,images` — for longlist entries that came from a hashtag.

Write `{out_file}`:

```
## IMAGES
<one block per post:
url
type
displayUrl
images: <every images[] URL verbatim, in slide order, comma-separated>
>

## NOTES
<any post whose images could not be retrieved>
```

Every URL verbatim — these are what the picker page renders and what the screener downloads, so a mangled URL is a dead candidate. Print a two-line summary and stop.
