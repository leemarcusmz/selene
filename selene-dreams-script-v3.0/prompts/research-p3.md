<!-- VERSION: 2026-09-30.v2 -->
<!-- v2: research lane v2.1 — the longlist skips already-offered/picked posts and goes wide on fresh accounts; 35-50 instead of 25-35. The 2026-09-28 dry run showed phase 3 was the binding constraint: images for only 35 of ~173 posts, and after the hard exclude just 10 eligible, 1 from a fresh account. v1 2026-08-13. -->
# PHASE 3 of 4 — image URLs for the candidate pool

Read `{step1_file}` (raw posts and hashtag items).

First decide, from the raw lines alone, a LONGLIST of 35-50 posts that could plausibly become carousel/image references for Selene. Prefer Sidecar/Image; Video only where a static cover is strong; no Reels. Err inclusive here — the next phase cuts, and the visual screener cuts harder. A post without images here is a post phase 4 cannot offer, so the longlist decides the ceiling of the week.

Two rules that shape the longlist (research lane v2.1):

{exclude_block}

{accounts_block}

- **Never longlist an excluded shortcode** — it cannot be offered, so fetching its images wastes the slot.
- **Go wide on fresh accounts**: longlist EVERY plausible on-brand post from an account marked fresh above (hashtag frontier included), before filling the remainder with tracked-brand posts; phase 4 needs at least 8 fresh-account candidates and can only choose from what has images.

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
