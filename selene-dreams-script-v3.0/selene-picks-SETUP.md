# Selene Picks — teammate selection setup (~10 min, one time)

The weekly shortlist becomes a shared web page. Teammates open one permanent
link, tick up to 5 posts (and which 3 slides for big carousels), and hit
Submit — **the first valid submission wins the week**, and the prompts are
generated into the Generation Queue automatically via your Mac.

## What's already done
- `picker.gs` (the web app) and `prompt_runner.py` + updated `server.py`
  (the /select endpoint) are in your v3.0 folder.
- The Monday research agent now also publishes `shortlists/shortlist-DATE.json`
  to your GitHub memory repo — the picker reads it from there. First one
  appears after next Monday's run.
- The prompt-writer skill respects the week lock (your chat picks count too).

## Your steps

**1. Add the picker to Apps Script**
Sheet → Extensions → Apps Script → **+ (Files) → Script**, name it `picker`,
paste the contents of `picker.gs`, save. (Same project as trigger.gs — it
reuses your WEBHOOK_URL/SECRET. Don't make a separate project.)

**2. Fill in your teammates' emails**
At the top of picker.gs, put their addresses into `TEAMMATE_EMAILS`.

**3. Check the GitHub token property**
Project Settings (gear) → Script Properties → make sure `GITHUB_TOKEN` exists
(value = the selene-ig-memory token, same as in github_token.txt). Add it if
missing.

**4. Deploy the web app**
Deploy → New deployment → type: **Web app** → Execute as: **Me** → Who has
access: **Anyone** → Deploy. Authorize when asked. **Copy the /exec URL** —
that's the permanent picker link (share it in your team chat too).

**5. Turn on the Monday invite email**
In the editor, function dropdown → `sendPickInvite`... no — choose
`installEmailTrigger` → Run. (Mondays ~10:30 the teammates get the link,
only when a fresh shortlist exists and nobody has picked yet.)

**6. Restart "Selene AI"**
Stop → Start, so the server loads the /select endpoint (the banner should
now also list `POST /select`).

## How a week flows
Mon 09:00 — research agent publishes report + gallery + shortlist JSON →
~10:30 invite email goes out → first teammate (or you) submits on the page →
your Mac writes the prompt rows (needs "Start Selene AI" running + claude CLI
logged in) → rows appear on Generation Status → you flip D=Ready per row →
images generate → G=Ready when you want captions → post.

## Notes & edge cases
- If your Mac is off at submission time, the pick still locks the week and is
  saved as PENDING in the Weekly Picks tab — ask Claude to "run the pending
  weekly pick" (or rerun via `python3 prompt_runner.py --json ...`) later.
- The 5-post and 3-slide limits are enforced in the page AND server-side.
- Names are honor-system (you chose link-access, no login).
- IG image URLs in the picker expire after a few weeks — same as the gallery;
  the page is freshest in week one, which is the only week it matters.
